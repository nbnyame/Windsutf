"""
CRM Case Folder Monitor
Watches the 'Create CRM Case' inbox subfolder in the shared mailbox.

If an email sits in that folder for longer than AGE_THRESHOLD_MINUTES without
being processed (moved out) by Copilot / Power Automate, it bounces the email:
  1. Moves it to 'Create CRM Case retry (ignore)'
  2. Marks it as unread
  3. Moves it back to 'Create CRM Case'
so that Copilot gets a second chance to pick it up.

The timer starts from when the email is FIRST SEEN in 'Create CRM Case' by
this monitor (not from receivedDateTime), so emails that were manually moved
into the folder long after receipt are timed correctly.

After each bounce the first-seen timer resets to now, so if Copilot still
fails to process it the email will be bounced again after another 10 minutes.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────

TENANT_ID     = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")

MAILBOX        = os.getenv("DRAFT_TARGET_MAILBOX", "supportcenter@winmarkcorporation.com")
SOURCE_FOLDER  = "Create CRM Case"
RETRY_FOLDER   = "Create CRM Case retry (ignore)"

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

AGE_THRESHOLD_MINUTES = 10   # bounce if email has been in folder longer than this
POLL_INTERVAL_SECONDS = 120  # check every 2 minutes

STATE_FILE = os.path.join(os.path.dirname(__file__), "crm_folder_state.json")

# ─── Logging ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "folder_monitor.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("crm_folder_monitor")


# ─── Monitor class ────────────────────────────────────────────────────────

class CRMCaseFolderMonitor:
    """Polls 'Create CRM Case' and bounces stale emails for Copilot retry."""

    def __init__(self):
        if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
            raise ValueError(
                "Missing required .env variables: AZURE_TENANT_ID, "
                "AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        self._token = None
        self._token_expires = 0
        self._first_seen: dict[str, str] = self._load_state().get("first_seen", {})

    # ── Azure AD token ────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }
        resp = requests.post(url, data=data, timeout=30)
        resp.raise_for_status()
        token_data = resp.json()
        self._token = token_data["access_token"]
        self._token_expires = time.time() + token_data.get("expires_in", 3600)
        log.info("Graph API token acquired/refreshed.")
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── State helpers (first_seen + cooldown) ────────────────────────────

    def _load_state(self) -> dict:
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump({"first_seen": self._first_seen}, f)

    def _record_first_seen(self, internet_id: str):
        """Record now as the first time we see this email in the folder (idempotent)."""
        if internet_id not in self._first_seen:
            self._first_seen[internet_id] = datetime.now(timezone.utc).isoformat()

    def _reset_first_seen(self, internet_id: str):
        """Reset the timer for an email (called after a bounce so the retry gets a fresh window)."""
        self._first_seen[internet_id] = datetime.now(timezone.utc).isoformat()

    def _remove_first_seen(self, internet_id: str):
        """Remove tracking for an email that has left the folder."""
        self._first_seen.pop(internet_id, None)

    def _folder_age(self, internet_id: str) -> timedelta:
        """How long this email has been in the folder according to our first-seen record."""
        ts = self._first_seen.get(internet_id)
        if not ts:
            return timedelta(0)
        return datetime.now(timezone.utc) - datetime.fromisoformat(ts)

    # ── Graph API helpers ─────────────────────────────────────────────────

    def _get_inbox_child_folder_id(self, headers: dict, folder_name: str) -> str | None:
        """Return the ID of a direct child folder of Inbox, or None if not found."""
        url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/Inbox/childFolders"
            f"?$top=50&$select=id,displayName"
        )
        while url:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for f in data.get("value", []):
                if f.get("displayName") == folder_name:
                    return f["id"]
            url = data.get("@odata.nextLink")
        return None

    def _move_message(self, headers: dict, msg_id: str, dest_folder_id: str) -> dict:
        resp = requests.post(
            f"{GRAPH_BASE}/users/{MAILBOX}/messages/{msg_id}/move",
            headers=headers,
            json={"destinationId": dest_folder_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _mark_unread(self, headers: dict, msg_id: str):
        resp = requests.patch(
            f"{GRAPH_BASE}/users/{MAILBOX}/messages/{msg_id}",
            headers=headers,
            json={"isRead": False},
            timeout=30,
        )
        resp.raise_for_status()

    # ── Main check ────────────────────────────────────────────────────────

    def check_and_retry(self) -> int:
        """
        Scan 'Create CRM Case' for all current emails, record first-seen timestamps,
        and bounce any that have been in the folder longer than AGE_THRESHOLD_MINUTES.
        Returns the number of emails bounced.
        """
        headers = self._headers()

        source_id = self._get_inbox_child_folder_id(headers, SOURCE_FOLDER)
        retry_id  = self._get_inbox_child_folder_id(headers, RETRY_FOLDER)

        if not source_id:
            log.error(f"Folder '{SOURCE_FOLDER}' not found under Inbox.")
            return 0
        if not retry_id:
            log.error(f"Folder '{RETRY_FOLDER}' not found under Inbox.")
            return 0

        # Fetch ALL emails currently in the folder
        msgs_url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{source_id}/messages"
            f"?$select=id,subject,receivedDateTime,internetMessageId,isRead"
            f"&$top=50"
        )
        resp = requests.get(msgs_url, headers=headers, timeout=30)
        resp.raise_for_status()
        messages = resp.json().get("value", [])

        # Track which internet IDs are currently in the folder
        current_ids: set[str] = set()
        for msg in messages:
            iid = msg.get("internetMessageId") or msg["id"]
            current_ids.add(iid)
            self._record_first_seen(iid)  # no-op if already recorded

        # Remove first_seen entries for emails that have left the folder (processed by Copilot)
        gone = [iid for iid in self._first_seen if iid not in current_ids]
        for iid in gone:
            self._remove_first_seen(iid)

        self._save_state()

        if not messages:
            return 0

        bounced = 0
        threshold = timedelta(minutes=AGE_THRESHOLD_MINUTES)

        for msg in messages:
            msg_id      = msg["id"]
            internet_id = msg.get("internetMessageId") or msg_id
            subject     = msg.get("subject", "(no subject)")

            age = self._folder_age(internet_id)
            if age < threshold:
                continue  # not old enough yet

            log.info(
                f"  Bouncing: '{subject}' "
                f"(in folder for {str(age).split('.')[0]})"
            )

            try:
                # Step 1 — move to retry folder
                moved1 = self._move_message(headers, msg_id, retry_id)
                retry_msg_id = moved1.get("id", msg_id)
                time.sleep(5)

                # Step 2 — mark as unread
                self._mark_unread(headers, retry_msg_id)

                # Step 3 — move back to 'Create CRM Case'
                time.sleep(5)
                self._move_message(headers, retry_msg_id, source_id)

                # Reset first-seen so the retry gets a fresh 10-min window
                self._reset_first_seen(internet_id)
                self._save_state()
                log.info(f"  Bounced successfully.")
                bounced += 1

            except Exception as e:
                log.error(f"  Failed to bounce '{subject}': {e}")

        return bounced

    # ── Run loop ──────────────────────────────────────────────────────────

    def run(self):
        log.info("=" * 60)
        log.info("CRM Case Folder Monitor starting")
        log.info(f"Watching : {MAILBOX} / Inbox / {SOURCE_FOLDER}")
        log.info(f"Threshold: {AGE_THRESHOLD_MINUTES} min  |  Cooldown: {COOLDOWN_MINUTES} min")
        log.info(f"Interval : {POLL_INTERVAL_SECONDS}s")
        log.info("=" * 60)

        while True:
            try:
                bounced = self.check_and_retry()
                if bounced:
                    log.info(f"Bounced {bounced} email(s) this cycle.")
            except Exception as e:
                log.error(f"Unexpected error in monitor cycle: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


# ─── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    monitor = CRMCaseFolderMonitor()
    monitor.run()
