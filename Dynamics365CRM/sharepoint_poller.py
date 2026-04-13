"""
SharePoint → Dynamics 365 CRM Case Creator
Polls a SharePoint list for approved items and creates CRM cases automatically.
"""

import os
import re
import sys
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))  # seconds

# Azure AD / Graph API
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")

# SharePoint
SHAREPOINT_HOSTNAME = "winmarkcorporation605.sharepoint.com"
SHAREPOINT_SITE_PATH = "/sites/MarketingTemp"
SHAREPOINT_LIST_NAME = os.getenv("SHAREPOINT_LIST_NAME", "Store info")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ─── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "poller.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("sharepoint_poller")


class SharePointPoller:
    """Polls SharePoint list and creates CRM cases for approved items."""

    def __init__(self):
        self._validate_config()
        self.token = None
        self.token_expires = 0
        self.site_id = None
        self.list_id = None

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

    # ─── SharePoint Discovery ────────────────────────────────────────────

    def _discover_site(self):
        """Find the SharePoint site ID."""
        if self.site_id:
            return self.site_id

        url = f"{GRAPH_BASE}/sites/{SHAREPOINT_HOSTNAME}:{SHAREPOINT_SITE_PATH}"
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()
        self.site_id = resp.json()["id"]
        log.info(f"SharePoint site ID: {self.site_id}")
        return self.site_id

    def _discover_list(self):
        """Find the SharePoint list ID by name."""
        if self.list_id:
            return self.list_id

        site_id = self._discover_site()
        url = f"{GRAPH_BASE}/sites/{site_id}/lists"
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()

        for lst in resp.json().get("value", []):
            if lst["displayName"].lower() == SHAREPOINT_LIST_NAME.lower():
                self.list_id = lst["id"]
                log.info(f"SharePoint list '{SHAREPOINT_LIST_NAME}' ID: {self.list_id}")
                return self.list_id

        raise ValueError(
            f"List '{SHAREPOINT_LIST_NAME}' not found. "
            f"Available: {[l['displayName'] for l in resp.json().get('value', [])]}"
        )

    # ─── Read / Update Items ─────────────────────────────────────────────

    def get_approved_items(self):
        """Fetch items from SharePoint where Status == 'Approved'."""
        site_id = self._discover_site()
        list_id = self._discover_list()

        # Paginate through all items and filter client-side
        all_approved = []
        url = (
            f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"
            f"?$expand=fields&$top=200"
        )
        while url:
            resp = requests.get(url, headers=self._graph_headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                status = str(item.get("fields", {}).get("Status", "")).strip().lower()
                if status == "approved":
                    all_approved.append(item)
            url = data.get("@odata.nextLink")
        return all_approved

    def update_item_status(self, item_id, status, error_msg=None):
        """Update the Status column of a SharePoint list item."""
        site_id = self._discover_site()
        list_id = self._discover_list()

        url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
        fields = {"Status": status}

        resp = requests.patch(
            url, headers=self._graph_headers(), json=fields, timeout=30
        )
        resp.raise_for_status()
        log.info(f"Item {item_id} status updated to '{status}'.")

    # ─── Map SharePoint → CRM ────────────────────────────────────────────

    @staticmethod
    def map_item_to_case(fields):
        """Map SharePoint list fields to CRM case parameters."""
        # Build received_on from Dateandtime + Time columns
        date_val = fields.get("Dateandtime", "")
        time_val = str(fields.get("Time", "")).strip()
        received_on = None
        if date_val:
            try:
                date_str = str(date_val).strip()
                if "T" in date_str:
                    dt = datetime.fromisoformat(date_str.replace("Z", ""))
                    date_str = dt.strftime("%m/%d/%Y")

                # Check if date already contains a time (e.g. "4/13/2026 6:00 am")
                has_time = bool(re.search(r'\d{1,2}:\d{2}\s*[AaPp][Mm]', date_str))

                if has_time:
                    # Date already has time embedded, use as-is
                    # Extract just date + first time occurrence
                    m = re.match(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AaPp][Mm])', date_str)
                    received_on = m.group(1) if m else date_str
                elif time_val:
                    # Clean duplicated time values (e.g. "06:00 am 06:00 am")
                    time_match = re.match(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', time_val)
                    if time_match:
                        time_val = time_match.group(1)
                    received_on = f"{date_str} {time_val}"
                else:
                    received_on = date_str
            except Exception:
                received_on = str(date_val)

        # Map origin text/code to CRM code
        origin_map = {
            "phone": 1, "p": 1,
            "email": 2, "e": 2,
            "web": 3, "w": 3,
            "voice to text": 100000000, "v": 100000000,
            "internal": 100000001, "i": 100000001,
            "splunk": 100000001, "s": 100000001,
        }
        origin_text = str(fields.get("Origin", "")).strip().lower()
        origin_code = origin_map.get(origin_text)

        # Map priority text/code to CRM code
        priority_map = {
            "normal": 2, "n": 2,
            "emergency": 100000000, "e": 100000000,
            "immediate": 100000001, "i": 100000001,
            "development": 100000002, "d": 100000002,
            "moderate": 100000003, "m": 100000003,
            "customer service": 100000004, "c": 100000004,
        }
        priority_text = str(fields.get("Priority", "normal")).strip().lower()
        priority_code = priority_map.get(priority_text, 2)

        # Store number comes as float (e.g. 11407.0) — convert to clean string
        raw_store = fields.get("Storenumber", "")
        try:
            store_number = str(int(float(raw_store)))
        except (ValueError, TypeError):
            store_number = str(raw_store).strip()

        return {
            "store_number": store_number,
            "contact": str(fields.get("Contactperson", "")).strip() or None,
            "contact_phone": str(fields.get("Phonenumber", "")).strip() or None,
            "description": str(fields.get("Summary", "")).strip(),
            "subject": str(fields.get("Subject", "")).strip() or None,
            "case_type": str(fields.get("Case", "")).strip() or None,
            "origin": origin_code,
            "received_on": received_on,
            "priority": priority_code,
        }

    # ─── Main Loop ───────────────────────────────────────────────────────

    def process_approved_items(self, crm_client):
        """Fetch approved items and create CRM cases."""
        items = self.get_approved_items()
        if not items:
            return 0

        log.info(f"Found {len(items)} approved item(s) to process.")
        processed = 0

        for item in items:
            item_id = item["id"]
            fields = item.get("fields", {})
            raw_store = fields.get("Storenumber", "?")
            try:
                store = str(int(float(raw_store)))
            except (ValueError, TypeError):
                store = str(raw_store)

            try:
                # Mark as in-progress
                self.update_item_status(item_id, "Processing")

                # Map fields and create case
                case_params = self.map_item_to_case(fields)
                log.info(f"Creating case for store {case_params['store_number']}...")
                log.info(f"  Params: contact={case_params.get('contact')}, "
                         f"phone={case_params.get('contact_phone')}, "
                         f"subject={case_params.get('subject')}, "
                         f"case_type={case_params.get('case_type')}")

                result = crm_client.create_case(**case_params)

                # Mark as processed
                self.update_item_status(item_id, "Processed")
                log.info(
                    f"Case created for store {case_params['store_number']}: "
                    f"{result.get('case_id', '?')}"
                )
                processed += 1

            except Exception as e:
                log.error(f"Failed to process item {item_id} (store {store}): {e}")
                try:
                    self.update_item_status(item_id, "Failed", str(e))
                except Exception:
                    log.error(f"Could not update status for item {item_id}")

        return processed

    def run(self):
        """Main polling loop."""
        from crm_client import Dynamics365Client

        log.info("=" * 60)
        log.info("SharePoint -> CRM Case Poller starting")
        log.info(f"Poll interval: {POLL_INTERVAL}s")
        log.info(f"SharePoint list: {SHAREPOINT_LIST_NAME}")
        log.info("=" * 60)

        # Authenticate CRM once
        crm = Dynamics365Client()
        crm.authenticate()
        last_auth = time.time()

        # Discover SharePoint site/list
        self._discover_site()
        self._discover_list()

        log.info("Ready. Polling for approved items...\n")

        while True:
            try:
                # Re-authenticate CRM every 30 minutes to keep session alive
                if time.time() - last_auth > 1800:
                    log.info("Re-authenticating CRM session...")
                    crm.authenticate()
                    last_auth = time.time()

                count = self.process_approved_items(crm)
                if count:
                    log.info(f"Processed {count} case(s) this cycle.\n")

            except KeyboardInterrupt:
                log.info("Shutting down.")
                break
            except Exception as e:
                log.error(f"Error in poll cycle: {e}")

            time.sleep(POLL_INTERVAL)


# ─── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SharePoint → CRM Case Poller")
    parser.add_argument(
        "--once", action="store_true",
        help="Run one poll cycle and exit (don't loop)",
    )
    parser.add_argument(
        "--interval", type=int, default=None,
        help="Override poll interval in seconds",
    )
    parser.add_argument(
        "--test-connection", action="store_true",
        help="Test SharePoint and CRM connections, then exit",
    )
    args = parser.parse_args()

    if args.interval:
        POLL_INTERVAL = args.interval

    poller = SharePointPoller()

    if args.test_connection:
        log.info("Testing SharePoint connection...")
        poller._discover_site()
        poller._discover_list()
        items = poller.get_approved_items()
        log.info(f"Connection OK. {len(items)} approved item(s) found.")

        log.info("Testing CRM connection...")
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        log.info("CRM connection OK.")
        log.info("All connections verified!")

    elif args.once:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        poller._discover_site()
        poller._discover_list()
        count = poller.process_approved_items(crm)
        log.info(f"Done. Processed {count} item(s).")

    else:
        poller.run()
