"""
Splunk Alert Poller

Monitors Inbox → Internal Requests → Splunk Alerts → CF and Non-Start Point
for two automated Splunk email types and creates a CRM case per listed store.

  CF Late Stores Report:
    - Case type  : CF Late
    - Contact    : Internal
    - Summary    : "CF Late, last sent {Last Sent date}"   (per store)
    - Move to    : Inbox → Internal Requests

  DRSUS Update – Detected non-start point:
    - Case type  : Non-Start Point
    - Contact    : Splunk
    - Summary    : "Detected non-start point"
    - Move to    : Inbox → Internal Requests → Splunk Alerts

Duplicate check: skips a store if an active CRM case already exists today
for that store with the same case type.

Polls once per hour. Processed message IDs are persisted to a state file
so re-processing on restart is safe.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from crm_client import Dynamics365Client

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

TENANT_ID     = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
MAILBOX       = os.getenv("DRAFT_TARGET_MAILBOX", "supportcenter@winmarkcorporation.com")
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"

# Source folder: Inbox → Internal Requests → Splunk Alerts → CF and Non-Start Point
SOURCE_FOLDER_PATH = ["Internal Requests", "Splunk Alerts", "CF and Non-Start Point"]

# Destination folders after processing (path from Inbox children)
CF_LATE_DEST_PATH   = ["Internal Requests"]
NON_START_DEST_PATH = ["Internal Requests", "Splunk Alerts"]

POLL_INTERVAL_SECONDS = 3600  # once per hour

STATE_FILE = os.path.join(os.path.dirname(__file__), "splunk_alert_state.json")

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "splunk_alert_poller.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

# ── HTML text extractor ───────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Strip HTML tags, converting block/line elements to spaces."""
    _BLOCK = {"p", "br", "tr", "li", "div", "hr"}

    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._BLOCK:
            self._parts.append(" ")

    def handle_endtag(self, tag):
        if tag.lower() in self._BLOCK:
            self._parts.append(" ")

    def handle_data(self, data):
        self._parts.append(data)

    def handle_entityref(self, name):
        entities = {"nbsp": " ", "amp": "&", "lt": "<", "gt": ">", "quot": '"'}
        self._parts.append(entities.get(name, ""))

    def handle_charref(self, name):
        try:
            self._parts.append(chr(int(name[1:], 16) if name.startswith("x") else int(name)))
        except Exception:
            pass

    def get_text(self):
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def _strip_html(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.get_text()


# ── UTC → Central helper ──────────────────────────────────────────────────────

def _utc_to_central_str(utc_str: str) -> str:
    """
    Convert Graph API receivedDateTime (UTC, 'YYYY-MM-DDTHH:MM:SSZ') to a
    Central-time string ('MM/DD/YYYY HH:MM AM/PM') suitable for crm_client
    parse_received_on, which expects US Central input.
    """
    try:
        from zoneinfo import ZoneInfo
        dt_utc = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        dt_c = dt_utc.astimezone(ZoneInfo("America/Chicago"))
    except ImportError:
        # Python < 3.9 fallback: use same CDT/CST offset logic as crm_client
        from datetime import timedelta
        dt_utc = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
        year = dt_utc.year
        mar1 = datetime(year, 3, 1)
        cdt_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
        cdt_start = cdt_start.replace(hour=7)   # 2 AM Central = 7 AM UTC
        nov1 = datetime(year, 11, 1)
        cst_start = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
        cst_start = cst_start.replace(hour=8)   # 2 AM Central = 8 AM UTC
        offset_hours = -5 if cdt_start <= dt_utc < cst_start else -6
        from datetime import timezone as tz2, timedelta as td2
        dt_c = dt_utc + timedelta(hours=offset_hours)
    return dt_c.strftime("%m/%d/%Y %I:%M %p").lstrip("0")


# ── Main poller class ─────────────────────────────────────────────────────────

class SplunkAlertPoller:

    def __init__(self):
        self._processed_ids: set = set()
        self._load_state()

    # ── State ──────────────────────────────────────────────────────────────

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                self._processed_ids = set(data.get("processed_ids", []))
                log.info(f"Loaded state: {len(self._processed_ids)} processed ID(s).")
            except Exception as e:
                log.warning(f"Could not load state: {e}. Starting fresh.")
                self._processed_ids = set()
        else:
            self._processed_ids = set()

    def _save_state(self):
        ids_list = list(self._processed_ids)[-2000:]
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"processed_ids": ids_list}, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save state: {e}")

    def _mark_processed(self, internet_id: str):
        self._processed_ids.add(internet_id)
        self._save_state()

    # ── Auth ───────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
        resp = requests.post(url, data={
            "grant_type":    "client_credentials",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope":         "https://graph.microsoft.com/.default",
        }, timeout=30)
        resp.raise_for_status()
        token = resp.json()["access_token"]
        log.info("Graph API token acquired/refreshed.")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Graph API helpers ──────────────────────────────────────────────────

    def _graph_get(self, url: str, headers: dict,
                   retries: int = 3, backoff: int = 5) -> requests.Response:
        """GET with automatic retry on transient 5xx errors."""
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status >= 500 and attempt < retries:
                    log.warning(f"  Graph API {status} on attempt {attempt}/{retries}, retrying in {backoff}s...")
                    time.sleep(backoff)
                    last_exc = e
                else:
                    raise
        raise last_exc

    def _get_folder_id(self, headers: dict, path: list) -> str | None:
        """
        Walk from Inbox's child folders down a display-name path.
        e.g. ["Internal Requests", "Splunk Alerts", "CF and Non-Start Point"]
        """
        current_url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/Inbox/childFolders"
            f"?$top=50&$select=id,displayName"
        )
        folder_id = None
        for name in path:
            found_id = None
            page_url = current_url
            while page_url:
                data = self._graph_get(page_url, headers).json()
                for f in data.get("value", []):
                    if f.get("displayName") == name:
                        found_id = f["id"]
                        break
                if found_id:
                    break
                page_url = data.get("@odata.nextLink")
            if not found_id:
                log.error(f"Folder '{name}' not found under current path.")
                return None
            folder_id = found_id
            current_url = (
                f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{folder_id}/childFolders"
                f"?$top=50&$select=id,displayName"
            )
        return folder_id

    def _fetch_messages(self, headers: dict, folder_id: str) -> list:
        """Return all messages in folder, oldest first."""
        url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{folder_id}/messages"
            f"?$select=id,subject,receivedDateTime,internetMessageId"
            f"&$top=50&$orderby=receivedDateTime asc"
        )
        messages = []
        while url:
            data = self._graph_get(url, headers).json()
            messages.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return messages

    def _get_message_body(self, headers: dict, msg_id: str) -> str:
        """Fetch and return the plain-text content of a message body."""
        url = f"{GRAPH_BASE}/users/{MAILBOX}/messages/{msg_id}?$select=body"
        data = self._graph_get(url, headers).json()
        body = data.get("body", {})
        content = body.get("content", "")
        if body.get("contentType", "text").lower() == "html":
            return _strip_html(content)
        return re.sub(r"\s+", " ", content).strip()

    def _move_message(self, headers: dict, msg_id: str, dest_folder_id: str):
        url = f"{GRAPH_BASE}/users/{MAILBOX}/messages/{msg_id}/move"
        resp = requests.post(
            url, headers=headers,
            json={"destinationId": dest_folder_id},
            timeout=30,
        )
        resp.raise_for_status()

    # ── Email type detection ───────────────────────────────────────────────

    @staticmethod
    def _email_type(subject: str) -> str | None:
        """Return 'cf_late', 'non_start_point', or None."""
        s = subject.lower()
        if "cf late" in s:
            return "cf_late"
        if "non-start point" in s or "non start point" in s:
            return "non_start_point"
        return None

    # ── Body parsers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_cf_late(body_text: str) -> list:
        """
        Extract store numbers and per-store Last Sent dates from a CF Late body.
        Returns list of {"store": "11253", "last_sent": "05/24/2026"}.
        """
        results = []
        seen = set()
        # Match 5-digit store number, then (name + days), then first MM/DD/YYYY date
        pattern = re.compile(r"\b(\d{5})\s+[A-Za-z&].+?(\d{2}/\d{2}/\d{4})", re.DOTALL)
        for m in pattern.finditer(body_text):
            store = m.group(1)
            last_sent = m.group(2)
            if store not in seen:
                seen.add(store)
                results.append({"store": store, "last_sent": last_sent})
        return results

    @staticmethod
    def _parse_non_start_point(body_text: str) -> list:
        """
        Extract store numbers from a Detected non-start point email body.
        Returns list of unique store number strings.
        """
        seen = set()
        stores = []
        pattern = re.compile(r"\b(\d{5})\s+SERVER\b")
        for m in pattern.finditer(body_text):
            store = m.group(1)
            if store not in seen:
                seen.add(store)
                stores.append(store)
        return stores

    # ── Duplicate check ────────────────────────────────────────────────────

    def _is_duplicate(self, crm: Dynamics365Client, store: str, case_type_code: int) -> dict | None:
        """
        Return existing active case dict if one was created today for
        this store with this case type, else None.
        """
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        params = {
            "$filter": (
                f"statecode eq 0 "
                f"and win_storenumber eq '{store}' "
                f"and casetypecode eq {case_type_code} "
                f"and createdon ge {today_utc}T00:00:00Z "
                f"and createdon lt {today_utc}T23:59:59Z"
            ),
            "$select": "incidentid,ticketnumber",
            "$top": 1,
            "$orderby": "createdon desc",
        }
        cases = crm._request("GET", "incidents", params=params).json().get("value", [])
        if cases:
            return {"case_id": cases[0]["incidentid"], "ticketnumber": cases[0]["ticketnumber"]}
        return None

    # ── Case creation ──────────────────────────────────────────────────────

    def _create_case(self, crm: Dynamics365Client, store: str, description: str,
                     case_type: str, contact: str, received_on: str) -> dict | None:
        try:
            result = crm.create_case(
                description=description,
                store_number=store,
                case_type=case_type,
                contact=contact,
                contact_phone=None,
                origin=100000001,   # Internal / Splunk
                received_on=received_on,
            )
            return result
        except ValueError as e:
            log.error(f"  Store {store}: account error — {e}")
            return None
        except Exception as e:
            log.error(f"  Store {store}: failed to create case — {e}")
            return None

    # ── Process one email ──────────────────────────────────────────────────

    def process_email(self, headers: dict, crm: Dynamics365Client, msg: dict,
                      cf_late_dest_id: str, non_start_dest_id: str) -> int:
        """Process one message. Returns number of CRM cases created."""
        subject     = msg.get("subject", "")
        msg_id      = msg["id"]
        internet_id = msg.get("internetMessageId") or msg_id
        received_utc = msg.get("receivedDateTime", "")

        email_type = self._email_type(subject)
        if not email_type:
            log.info(f"  Skipping unrecognised subject: '{subject}'")
            return 0

        log.info(f"Processing '{subject}' (type={email_type})")

        try:
            body_text = self._get_message_body(headers, msg_id)
        except Exception as e:
            log.error(f"  Could not fetch body: {e}")
            return 0

        received_on = _utc_to_central_str(received_utc) if received_utc else ""
        cases_created = 0

        if email_type == "cf_late":
            entries = self._parse_cf_late(body_text)
            log.info(f"  Found {len(entries)} store(s) in CF Late report.")
            if not entries:
                log.warning("  No store entries parsed — check email body format.")

            case_type_code = crm.resolve_case_type("cf late")

            for entry in entries:
                store     = entry["store"]
                last_sent = entry["last_sent"]
                description = f"CF Late, last sent {last_sent}"

                dup = self._is_duplicate(crm, store, case_type_code)
                if dup:
                    log.info(f"  Store {store}: duplicate {dup['ticketnumber']} — skipping.")
                    continue

                result = self._create_case(crm, store, description, "cf late", "Internal", received_on)
                if result:
                    log.info(f"  Store {store}: created {result['ticketnumber']} (ID: {result['case_id']})")
                    cases_created += 1

            try:
                self._move_message(headers, msg_id, cf_late_dest_id)
                log.info("  Email moved to Internal Requests.")
            except Exception as e:
                log.error(f"  Failed to move email: {e}")

        elif email_type == "non_start_point":
            stores = self._parse_non_start_point(body_text)
            log.info(f"  Found {len(stores)} store(s) in Non-Start Point alert.")
            if not stores:
                log.warning("  No store entries parsed — check email body format.")

            case_type_code = crm.resolve_case_type("non-start point")

            for store in stores:
                description = "Detected non-start point"

                dup = self._is_duplicate(crm, store, case_type_code)
                if dup:
                    log.info(f"  Store {store}: duplicate {dup['ticketnumber']} — skipping.")
                    continue

                result = self._create_case(crm, store, description, "non-start point", "Splunk", received_on)
                if result:
                    log.info(f"  Store {store}: created {result['ticketnumber']} (ID: {result['case_id']})")
                    cases_created += 1

            try:
                self._move_message(headers, msg_id, non_start_dest_id)
                log.info("  Email moved to Splunk Alerts.")
            except Exception as e:
                log.error(f"  Failed to move email: {e}")

        self._mark_processed(internet_id)
        return cases_created

    # ── Main run loop ──────────────────────────────────────────────────────

    def run(self):
        log.info("=" * 60)
        log.info("Splunk Alert Poller starting")
        log.info(f"Mailbox  : {MAILBOX}")
        log.info(f"Source   : Inbox / {' / '.join(SOURCE_FOLDER_PATH)}")
        log.info(f"CF Late  → Internal Requests  (case type: CF Late, contact: Internal)")
        log.info(f"Non-Start → Splunk Alerts      (case type: Non-Start Point, contact: Splunk)")
        log.info(f"Interval : {POLL_INTERVAL_SECONDS}s ({POLL_INTERVAL_SECONDS // 60} min)")
        log.info("=" * 60)

        while True:
            try:
                headers = self._headers()

                source_id = self._get_folder_id(headers, SOURCE_FOLDER_PATH)
                if not source_id:
                    log.error("Source folder not found. Retrying next cycle.")
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                cf_late_dest_id = self._get_folder_id(headers, CF_LATE_DEST_PATH)
                non_start_dest_id = self._get_folder_id(headers, NON_START_DEST_PATH)
                if not cf_late_dest_id or not non_start_dest_id:
                    log.error("Destination folder(s) not found. Retrying next cycle.")
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                crm = Dynamics365Client()
                messages = self._fetch_messages(headers, source_id)

                if not messages:
                    log.info("No messages in folder.")
                else:
                    log.info(f"Found {len(messages)} message(s) in folder.")
                    total_created = 0
                    for msg in messages:
                        iid = msg.get("internetMessageId") or msg["id"]
                        if iid in self._processed_ids:
                            log.info(f"  Already processed: '{msg.get('subject', '')}' — skipping.")
                            continue
                        total_created += self.process_email(
                            headers, crm, msg, cf_late_dest_id, non_start_dest_id
                        )
                    if total_created:
                        log.info(f"Total cases created this cycle: {total_created}")

            except Exception as e:
                log.error(f"Unexpected error in poller cycle: {e}")

            log.info(f"Sleeping {POLL_INTERVAL_SECONDS}s until next check...")
            time.sleep(POLL_INTERVAL_SECONDS)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SplunkAlertPoller().run()
