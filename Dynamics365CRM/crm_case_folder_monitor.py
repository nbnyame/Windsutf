"""
CRM Case Folder Monitor
Watches the 'Create CRM Case' inbox subfolder in the shared mailbox.

Three-stage handling for emails that Copilot / Power Automate fails to process:

  Stage 1 — 'Create CRM Case' folder:
    If an email has been there for >= MOVE_TO_RETRY_MINUTES (10 min), move it
    to the 'Retry' subfolder (child of 'Create CRM Case') and mark it as READ
    so Copilot can retry processing.

  Stage 2 — 'Create CRM Case/Retry' folder:
    If an email has been there for >= MOVE_TO_RETRY2_MINUTES (10 min) without
    Copilot picking it up, move it to the 'Retry 2' subfolder for a second retry.

  Stage 3 — 'Create CRM Case/Retry 2' folder:
    If an email has been there for >= MOVE_TO_INBOX_MINUTES (7 min) without
    Copilot picking it up, move it to the main Inbox for manual handling.

Timers are based on first-seen by this monitor (not receivedDateTime).
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

MAILBOX          = os.getenv("DRAFT_TARGET_MAILBOX", "supportcenter@winmarkcorporation.com")
SOURCE_FOLDER    = "Create CRM Case"   # Inbox child
RETRY_SUBFOLDER  = "Retry"             # child of SOURCE_FOLDER
RETRY2_SUBFOLDER = "Retry 2"           # child of SOURCE_FOLDER

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

MOVE_TO_RETRY_MINUTES  = 10  # in SOURCE_FOLDER this long  → move to Retry,   mark read
MOVE_TO_RETRY2_MINUTES = 10  # in RETRY_SUBFOLDER this long → move to Retry 2
MOVE_TO_INBOX_MINUTES  = 7   # in RETRY2_SUBFOLDER this long → move to Inbox
POLL_INTERVAL_SECONDS = 60   # check every 1 minute

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

    def _get_child_folder_id(self, headers: dict, parent_folder_id: str, folder_name: str) -> str | None:
        """Return the ID of a named child folder under any parent folder ID."""
        url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{parent_folder_id}/childFolders"
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

    def _mark_read(self, headers: dict, msg_id: str):
        resp = requests.patch(
            f"{GRAPH_BASE}/users/{MAILBOX}/messages/{msg_id}",
            headers=headers,
            json={"isRead": True},
            timeout=30,
        )
        resp.raise_for_status()

    # ── Main check ────────────────────────────────────────────────────────

    def _scan_folder(self, headers: dict, folder_id: str, threshold_minutes: int,
                      dest_folder_id: str, dest_label: str,
                      mark_read: bool, all_seen_ids: set) -> int:
        """
        Scan a folder, record first-seen times, and move emails older than
        threshold_minutes to dest_folder_id.
        Returns count of emails moved.
        """
        msgs_url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{folder_id}/messages"
            f"?$select=id,subject,receivedDateTime,internetMessageId,isRead"
            f"&$top=50"
        )
        resp = requests.get(msgs_url, headers=headers, timeout=30)
        resp.raise_for_status()
        messages = resp.json().get("value", [])

        for msg in messages:
            iid = msg.get("internetMessageId") or msg["id"]
            all_seen_ids.add(iid)
            self._record_first_seen(iid)

        moved = 0
        threshold = timedelta(minutes=threshold_minutes)

        for msg in messages:
            msg_id      = msg["id"]
            internet_id = msg.get("internetMessageId") or msg_id
            subject     = msg.get("subject", "(no subject)")

            age = self._folder_age(internet_id)
            if age < threshold:
                continue

            log.info(
                f"  Moving to {dest_label}: '{subject}' "
                f"(in folder for {str(age).split('.')[0]})"
            )
            try:
                result = self._move_message(headers, msg_id, dest_folder_id)
                new_id = result.get("id", msg_id)
                time.sleep(5)

                if mark_read:
                    self._mark_read(headers, new_id)

                self._reset_first_seen(internet_id)
                moved += 1
                log.info(f"  Moved successfully.")
            except Exception as e:
                log.error(f"  Failed to move '{subject}': {e}")

        return moved

    def check_and_retry(self) -> int:
        """
        Stage 1: emails in 'Create CRM Case' >= 10 min → move to 'Retry',   mark read.
        Stage 2: emails in 'Create CRM Case/Retry' >= 10 min → move to 'Retry 2'.
        Stage 3: emails in 'Create CRM Case/Retry 2' >= 7 min  → move to Inbox.
        Returns total emails moved.
        """
        headers = self._headers()

        source_id = self._get_inbox_child_folder_id(headers, SOURCE_FOLDER)
        if not source_id:
            log.error(f"Folder '{SOURCE_FOLDER}' not found under Inbox.")
            return 0

        retry_id = self._get_child_folder_id(headers, source_id, RETRY_SUBFOLDER)
        if not retry_id:
            log.error(f"Subfolder '{RETRY_SUBFOLDER}' not found under '{SOURCE_FOLDER}'.")
            return 0

        retry2_id = self._get_child_folder_id(headers, source_id, RETRY2_SUBFOLDER)
        if not retry2_id:
            log.error(f"Subfolder '{RETRY2_SUBFOLDER}' not found under '{SOURCE_FOLDER}'.")
            return 0

        all_seen_ids: set[str] = set()

        # Stage 1: Create CRM Case → Retry (10 min, mark read)
        moved1 = self._scan_folder(
            headers, source_id, MOVE_TO_RETRY_MINUTES,
            retry_id, f"'{SOURCE_FOLDER}/{RETRY_SUBFOLDER}'",
            mark_read=True, all_seen_ids=all_seen_ids
        )

        # Stage 2: Retry → Retry 2 (10 min, no read change)
        moved2 = self._scan_folder(
            headers, retry_id, MOVE_TO_RETRY2_MINUTES,
            retry2_id, f"'{SOURCE_FOLDER}/{RETRY2_SUBFOLDER}'",
            mark_read=False, all_seen_ids=all_seen_ids
        )

        # Stage 3: Retry 2 → Inbox (7 min, no read change)
        moved3 = self._scan_folder(
            headers, retry2_id, MOVE_TO_INBOX_MINUTES,
            "inbox", "Inbox",
            mark_read=False, all_seen_ids=all_seen_ids
        )

        # Clean up first_seen for emails no longer in any watched folder
        gone = [iid for iid in self._first_seen if iid not in all_seen_ids]
        for iid in gone:
            self._remove_first_seen(iid)

        self._save_state()
        return moved1 + moved2 + moved3

    # ── Run loop ──────────────────────────────────────────────────────────

    def run(self):
        log.info("=" * 60)
        log.info("CRM Case Folder Monitor starting")
        log.info(f"Watching : {MAILBOX} / Inbox / {SOURCE_FOLDER}")
        log.info(f"Stage 1  : >={MOVE_TO_RETRY_MINUTES} min in '{SOURCE_FOLDER}' → move to '{RETRY_SUBFOLDER}' subfolder, mark read")
        log.info(f"Stage 2  : >={MOVE_TO_RETRY2_MINUTES} min in '{RETRY_SUBFOLDER}' → move to '{RETRY2_SUBFOLDER}' subfolder")
        log.info(f"Stage 3  : >={MOVE_TO_INBOX_MINUTES} min in '{RETRY2_SUBFOLDER}' → move to Inbox")
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
