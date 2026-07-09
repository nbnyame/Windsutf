"""
Splunk DRS Update Email Monitor -> Dynamics 365 CRM DRS Version Updater

Monitors the shared mailbox folder:
  Inbox -> INTERNAL REQUESTS -> Splunk Alerts -> Automate DRS Updates

For each unread email, parses the store number and DRS version from the subject:
  "{store} - Updated to DRS {version}, please update CRM"

Updates the DRS Version field on the CRM account, then moves the email to:
  Inbox -> INTERNAL REQUESTS -> Splunk Alerts

On failure: marks the email as read and leaves it in the folder for manual review.

Required environment variables (Dynamics365CRM/.env):
    AZURE_TENANT_ID       - Azure AD tenant ID
    AZURE_CLIENT_ID       - Azure AD app client ID
    AZURE_CLIENT_SECRET   - Azure AD app client secret
    DRS_MAILBOX           - Shared mailbox address (default: supportcenter@winmarkcorporation.com)
    CRM_DRS_VERSION_FIELD - CRM field name for DRS Version (default: win_drsversion1)
    DRS_POLL_INTERVAL     - Poll interval in seconds (default: 60)

NOTE: The Azure AD app registration needs these Microsoft Graph application permissions:
    Mail.Read, Mail.ReadWrite  (to access the shared mailbox)
"""

import os
import re
import sys
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("DRS_POLL_INTERVAL", "60"))

# Azure AD / Graph API
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")

# Shared mailbox to monitor
MAILBOX = os.getenv("DRS_MAILBOX", "supportcenter@winmarkcorporation.com")

# Folder paths (ordered list of display names to navigate)
MONITOR_FOLDER_PATH   = ["Inbox", "INTERNAL REQUESTS", "Splunk Alerts", "Automate DRS Updates"]
PROCESSED_FOLDER_PATH = ["Inbox", "INTERNAL REQUESTS", "Splunk Alerts"]

# CRM account field for DRS Version (OptionSet / dropdown)
CRM_DRS_VERSION_FIELD = os.getenv("CRM_DRS_VERSION_FIELD", "win_drsversion1")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Regex to parse email subject:
# "11733 - Updated to DRS 8.9.7 GENERAL (322), please update CRM"
SUBJECT_PATTERN = re.compile(
    r'^(\d+)\s*-\s*Updated to DRS\s+(.+?),\s*please update CRM',
    re.IGNORECASE,
)

# ─── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "drs_poller.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("drs_update_poller")


class DrsEmailPoller:
    """
    Monitors a shared mailbox folder for Splunk DRS update alert emails
    and updates the corresponding CRM account DRS Version field.
    """

    def __init__(self):
        self._validate_config()
        self.token = None
        self.token_expires = 0
        self._monitor_folder_id = None
        self._processed_folder_id = None
        self._inbox_folder_id = "inbox"  # Well-known name, always valid
        self._drs_option_map = None

    def _validate_config(self):
        missing = []
        if not TENANT_ID:
            missing.append("AZURE_TENANT_ID")
        if not CLIENT_ID:
            missing.append("AZURE_CLIENT_ID")
        if not CLIENT_SECRET:
            missing.append("AZURE_CLIENT_SECRET")
        if missing:
            raise ValueError(
                f"Missing required .env variables: {', '.join(missing)}\n"
                "Please add them to Dynamics365CRM/.env"
            )

    # ─── Graph API Auth ──────────────────────────────────────────────────

    def _get_token(self):
        """Acquire or refresh an Azure AD application token for Graph API."""
        if self.token and time.time() < self.token_expires - 60:
            return self.token

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
        self.token = token_data["access_token"]
        self.token_expires = time.time() + token_data.get("expires_in", 3600)
        log.info("Graph API token acquired/refreshed.")
        return self.token

    def _graph_headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ─── Folder Navigation ───────────────────────────────────────────────

    def _navigate_to_folder(self, folder_path):
        """
        Walk a folder path like ['Inbox', 'INTERNAL REQUESTS', 'Splunk Alerts'].
        Returns the Graph API folder ID of the deepest folder.
        """
        current_id = "inbox"  # Well-known name for Inbox
        for folder_name in folder_path[1:]:  # Inbox is the well-known root
            url = (
                f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{current_id}/childFolders"
                f"?$select=id,displayName&$top=100"
            )
            resp = requests.get(url, headers=self._graph_headers(), timeout=30)
            resp.raise_for_status()
            children = resp.json().get("value", [])
            match = next(
                (f for f in children if f["displayName"].lower() == folder_name.lower()),
                None,
            )
            if not match:
                available = [f["displayName"] for f in children]
                raise ValueError(
                    f"Folder '{folder_name}' not found. "
                    f"Available subfolders: {available}"
                )
            current_id = match["id"]
            log.info(f"Found folder '{folder_name}' (ID: {current_id})")
        return current_id

    def _discover_folders(self):
        """Resolve and cache the monitor and processed folder IDs."""
        if self._monitor_folder_id and self._processed_folder_id:
            return
        log.info(f"Locating monitor folder:   {' -> '.join(MONITOR_FOLDER_PATH)}")
        self._monitor_folder_id = self._navigate_to_folder(MONITOR_FOLDER_PATH)
        log.info(f"Locating processed folder: {' -> '.join(PROCESSED_FOLDER_PATH)}")
        self._processed_folder_id = self._navigate_to_folder(PROCESSED_FOLDER_PATH)
        log.info("Folder discovery complete.")

    # ─── Email Operations ────────────────────────────────────────────────

    def get_unread_emails(self):
        """Fetch all unread emails from the monitor folder, oldest first."""
        self._discover_folders()
        url = (
            f"{GRAPH_BASE}/users/{MAILBOX}"
            f"/mailFolders/{self._monitor_folder_id}/messages"
            f"?$filter=isRead eq false"
            f"&$select=id,subject,receivedDateTime,from"
            f"&$orderby=receivedDateTime asc"
            f"&$top=50"
        )
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def move_email(self, message_id, destination_folder_id):
        """Move a message to the specified folder."""
        url = f"{GRAPH_BASE}/users/{MAILBOX}/messages/{message_id}/move"
        resp = requests.post(
            url,
            headers=self._graph_headers(),
            json={"destinationId": destination_folder_id},
            timeout=30,
        )
        resp.raise_for_status()

    def mark_as_read(self, message_id):
        """Mark a message as read (leaves it in place)."""
        url = f"{GRAPH_BASE}/users/{MAILBOX}/messages/{message_id}"
        resp = requests.patch(
            url,
            headers=self._graph_headers(),
            json={"isRead": True},
            timeout=30,
        )
        resp.raise_for_status()

    # ─── Email Parsing ───────────────────────────────────────────────────

    @staticmethod
    def parse_subject(subject):
        """
        Parse store number and DRS version from the email subject.
        Expected: "{store} - Updated to DRS {version}, please update CRM"
        Returns: (store_number, drs_version) or (None, None) if no match.
        """
        match = SUBJECT_PATTERN.match(str(subject).strip())
        if not match:
            return None, None
        return match.group(1).strip(), match.group(2).strip()

    # ─── CRM DRS Version Option Map ──────────────────────────────────────

    def _load_drs_option_map(self, crm_client):
        """
        Fetch the DRS Version dropdown options from CRM metadata once and cache them.
        Maps lowercase label → integer option code.
        """
        if self._drs_option_map is not None:
            return self._drs_option_map
        log.info(
            f"Fetching DRS Version option set from CRM field '{CRM_DRS_VERSION_FIELD}'..."
        )
        try:
            self._drs_option_map = crm_client.get_option_set_values(
                "account", CRM_DRS_VERSION_FIELD
            )
            log.info(
                f"DRS Version options loaded: "
                + ", ".join(
                    f"'{k}' -> {v}" for k, v in self._drs_option_map.items()
                )
            )
        except Exception as e:
            log.warning(
                f"Could not load DRS Version option set: {e}\n"
                f"Will attempt to pass the version string directly as an integer value.\n"
                f"Run with --discover-fields <store> to inspect the CRM field."
            )
            self._drs_option_map = {}
        return self._drs_option_map

    def _resolve_drs_version(self, version_label, crm_client):
        """
        Map a DRS version label from SharePoint to the CRM OptionSet integer code.
        Falls back to direct integer parsing if the option map is unavailable.
        """
        option_map = self._load_drs_option_map(crm_client)
        label_lower = str(version_label).strip().lower()

        if option_map:
            if label_lower in option_map:
                return option_map[label_lower]
            # Try prefix match (e.g. "8.9.7" matching "8.9.7 general (322)")
            prefix_matches = {k: v for k, v in option_map.items() if k.startswith(label_lower)}
            if len(prefix_matches) == 1:
                matched_label = next(iter(prefix_matches))
                log.info(f"Prefix-matched '{version_label}' -> '{matched_label}'")
                return next(iter(prefix_matches.values()))
            if len(prefix_matches) > 1:
                # Prefer the latest 'general' release over preview builds
                general = {k: v for k, v in prefix_matches.items() if "general" in k}
                if general:
                    # Pick the highest-numbered general release
                    best_label = max(general.keys())
                    log.info(
                        f"Multiple matches for '{version_label}'; "
                        f"selected general release: '{best_label}'"
                    )
                    return general[best_label]
                # Fall back to highest-numbered match
                best_label = max(prefix_matches.keys())
                log.info(
                    f"Multiple matches for '{version_label}'; "
                    f"selected: '{best_label}'"
                )
                return prefix_matches[best_label]
            log.error(
                f"DRS version '{version_label}' not found in CRM option set. "
                f"Available: {list(option_map.keys())}"
            )
            raise ValueError(
                f"DRS version '{version_label}' does not match any CRM option. "
                f"Available: {list(option_map.keys())}"
            )
        else:
            # No option map — try direct integer
            try:
                return int(version_label)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cannot resolve DRS version '{version_label}' to a CRM option code. "
                    f"Set CRM_DRS_VERSION_FIELD correctly and ensure metadata is accessible."
                )

    # ─── Main Processing ─────────────────────────────────────────────────

    def process_emails(self, crm_client):
        """Process all unread DRS update emails in the monitor folder."""
        emails = self.get_unread_emails()
        if not emails:
            return 0

        log.info(f"Found {len(emails)} unread email(s) to process.")
        processed = 0

        for email in emails:
            message_id = email["id"]
            subject = email.get("subject", "")
            received = email.get("receivedDateTime", "")
            sender = email.get("from", {}).get("emailAddress", {}).get("address", "")

            store_number, drs_version_label = self.parse_subject(subject)

            if not store_number or not drs_version_label:
                log.warning(
                    f"Skipping unrecognized email: '{subject}' "
                    f"(from {sender}) — marking as read."
                )
                self.mark_as_read(message_id)
                continue

            log.info(
                f"Processing: store={store_number}, "
                f"DRS version='{drs_version_label}' (received {received})"
            )

            try:
                # Look up the CRM account by store number
                account = crm_client.lookup_account_by_store(store_number)
                account_id = account["accountid"]
                account_name = account.get("name", store_number)
                log.info(f"Found CRM account: {account_name} (ID: {account_id})")

                # Resolve the DRS version label to a CRM OptionSet code
                drs_version_code = self._resolve_drs_version(drs_version_label, crm_client)
                log.info(f"Resolved '{drs_version_label}' -> code {drs_version_code}")

                # Update the DRS Version field on the account
                crm_client.update_account(
                    account_id,
                    **{CRM_DRS_VERSION_FIELD: drs_version_code}
                )
                log.info(
                    f"Store {store_number} ({account_name}): "
                    f"DRS Version updated to '{drs_version_label}'."
                )

                # Mark as read then move to the processed folder
                self.mark_as_read(message_id)
                self.move_email(message_id, self._processed_folder_id)
                log.info(f"Email marked as read and moved to '{PROCESSED_FOLDER_PATH[-1]}'.")
                processed += 1

            except Exception as e:
                log.error(f"Failed to process email for store {store_number}: {e}")
                try:
                    self.move_email(message_id, self._inbox_folder_id)
                    log.info("Email left unread and moved to Inbox for manual review.")
                except Exception:
                    log.error("Could not move failed email to Inbox.")

        return processed

    def run(self):
        """Main polling loop."""
        from crm_client import Dynamics365Client

        log.info("=" * 60)
        log.info("Splunk DRS Email Monitor -> CRM DRS Version Updater")
        log.info(f"Mailbox:        {MAILBOX}")
        log.info(f"Monitor folder: {' -> '.join(MONITOR_FOLDER_PATH)}")
        log.info(f"Processed dest: {' -> '.join(PROCESSED_FOLDER_PATH)}")
        log.info(f"CRM field:      {CRM_DRS_VERSION_FIELD}")
        log.info(f"Poll interval:  {POLL_INTERVAL}s")
        log.info("=" * 60)

        crm = Dynamics365Client()
        crm.authenticate()
        last_auth = time.time()

        self._discover_folders()
        self._load_drs_option_map(crm)

        log.info("Ready. Polling for new DRS update emails...\n")

        while True:
            try:
                if time.time() - last_auth > 1800:
                    log.info("Re-authenticating CRM session...")
                    crm.authenticate()
                    last_auth = time.time()

                count = self.process_emails(crm)
                if count:
                    log.info(f"Processed {count} DRS update(s) this cycle.\n")

            except KeyboardInterrupt:
                log.info("Shutting down.")
                break
            except Exception as e:
                log.error(f"Error in poll cycle: {e}")

            time.sleep(POLL_INTERVAL)


# ─── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Splunk DRS Email Monitor -> CRM DRS Version Updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python drs_update_poller.py                       Start the continuous poller
  python drs_update_poller.py --once                Run one cycle and exit
  python drs_update_poller.py --test-connection     Verify mailbox + CRM connections
  python drs_update_poller.py --list-drs-versions   List available DRS Version options in CRM
  python drs_update_poller.py --list-emails         Show unread emails in the monitor folder
        """,
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit")
    parser.add_argument("--interval", type=int, default=None,
                        help="Override poll interval in seconds")
    parser.add_argument("--test-connection", action="store_true",
                        help="Test mailbox and CRM connections, then exit")
    parser.add_argument("--list-drs-versions", action="store_true",
                        help="List available DRS Version options from CRM metadata")
    parser.add_argument("--list-emails", action="store_true",
                        help="List unread emails currently in the monitor folder")
    args = parser.parse_args()

    if args.interval:
        POLL_INTERVAL = args.interval

    poller = DrsEmailPoller()

    if args.test_connection:
        log.info("Testing mailbox access...")
        poller._discover_folders()
        emails = poller.get_unread_emails()
        log.info(f"Mailbox OK. {len(emails)} unread email(s) in monitor folder.")

        log.info("Testing CRM connection...")
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        log.info("CRM OK.")
        log.info("All connections verified!")

    elif args.list_drs_versions:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        log.info(f"Fetching DRS Version options for field '{CRM_DRS_VERSION_FIELD}'...")
        try:
            options = crm.get_option_set_values("account", CRM_DRS_VERSION_FIELD)
            print(f"\nAvailable DRS Version options ({len(options)}):")
            for label, code in sorted(options.items(), key=lambda x: x[1]):
                print(f"  [{code}] {label}")
        except Exception as e:
            print(f"Error: {e}")

    elif args.list_emails:
        poller._discover_folders()
        emails = poller.get_unread_emails()
        if not emails:
            print("No unread emails in the monitor folder.")
        else:
            print(f"\n{len(emails)} unread email(s):\n")
            for e in emails:
                store, version = DrsEmailPoller.parse_subject(e.get("subject", ""))
                print(
                    f"  [{e.get('receivedDateTime', '')}]"
                    f"  Store={store or '?'}  Version={version or '?'}"
                    f"\n    Subject: {e.get('subject', '')}"
                )

    elif args.once:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        poller._discover_folders()
        count = poller.process_emails(crm)
        log.info(f"Done. Processed {count} DRS update(s).")

    else:
        poller.run()
