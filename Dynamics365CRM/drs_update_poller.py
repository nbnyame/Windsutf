"""
SharePoint "Splunk DRS Update" → Dynamics 365 CRM DRS Version Updater

Polls the "Splunk DRS Update" SharePoint list for items with Status = "Pending".
For each pending item, looks up the store account in CRM and updates the
DRS Version field in the Hardware, Software & Networking info section.

Environment variables (add to Dynamics365CRM/.env):
    AZURE_TENANT_ID          — Azure AD tenant ID (shared with sharepoint_poller)
    AZURE_CLIENT_ID          — Azure AD app client ID
    AZURE_CLIENT_SECRET      — Azure AD app client secret
    DRS_LIST_NAME            — SharePoint list name (default: "Splunk DRS Update")
    DRS_SHAREPOINT_SITE_PATH — SharePoint site path (default: /sites/MarketingTemp)
    CRM_DRS_VERSION_FIELD    — CRM API field name for DRS Version (default: win_drsversion)
    DRS_POLL_INTERVAL        — Poll interval in seconds (default: 60)

Run --discover-fields <store_number> to inspect account fields and confirm
the correct CRM field name for DRS Version.
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("DRS_POLL_INTERVAL", "60"))

# Azure AD / Graph API
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")

# SharePoint
SHAREPOINT_HOSTNAME = "winmarkcorporation605.sharepoint.com"
SHAREPOINT_SITE_PATH = os.getenv("DRS_SHAREPOINT_SITE_PATH", "/sites/MarketingTemp")
SHAREPOINT_LIST_NAME = os.getenv("DRS_LIST_NAME", "Splunk DRS Update")

# CRM account field for DRS Version (OptionSet / dropdown)
# Run: python drs_update_poller.py --discover-fields <store_number>
# to inspect all fields on an account and confirm this name.
CRM_DRS_VERSION_FIELD = os.getenv("CRM_DRS_VERSION_FIELD", "win_drsversion1")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# SharePoint column internal names for the "Splunk DRS Update" list.
# Override these env vars if your list uses different column names.
SP_FIELD_STORE_NUMBER = os.getenv("DRS_SP_STORE_FIELD", "StoreNumber")
SP_FIELD_DRS_VERSION  = os.getenv("DRS_SP_VERSION_FIELD", "DRSVersion")
SP_FIELD_STATUS       = os.getenv("DRS_SP_STATUS_FIELD", "Status")

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


class DrsUpdatePoller:
    """
    Polls SharePoint "Splunk DRS Update" list and updates CRM account
    DRS Version field for each Pending item.
    """

    def __init__(self):
        self._validate_config()
        self.token = None
        self.token_expires = 0
        self.site_id = None
        self.list_id = None
        self._drs_option_map = None   # label (lower) → CRM int code

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
        if self.site_id:
            return self.site_id
        url = f"{GRAPH_BASE}/sites/{SHAREPOINT_HOSTNAME}:{SHAREPOINT_SITE_PATH}"
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()
        self.site_id = resp.json()["id"]
        log.info(f"SharePoint site ID: {self.site_id}")
        return self.site_id

    def _discover_list(self):
        if self.list_id:
            return self.list_id
        site_id = self._discover_site()
        url = f"{GRAPH_BASE}/sites/{site_id}/lists"
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()
        for lst in resp.json().get("value", []):
            if lst["displayName"].lower() == SHAREPOINT_LIST_NAME.lower():
                self.list_id = lst["id"]
                log.info(f"List '{SHAREPOINT_LIST_NAME}' ID: {self.list_id}")
                return self.list_id
        available = [l["displayName"] for l in resp.json().get("value", [])]
        raise ValueError(
            f"List '{SHAREPOINT_LIST_NAME}' not found on site '{SHAREPOINT_SITE_PATH}'.\n"
            f"Available lists: {available}\n"
            f"Set DRS_LIST_NAME and/or DRS_SHAREPOINT_SITE_PATH in your .env to override."
        )

    # ─── Read / Update Items ─────────────────────────────────────────────

    def get_pending_items(self):
        """Fetch all items from SharePoint where Status == 'Pending'."""
        site_id = self._discover_site()
        list_id = self._discover_list()

        # Paginate through all items and filter client-side
        all_pending = []
        url = (
            f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"
            f"?$expand=fields&$top=200"
        )
        while url:
            resp = requests.get(url, headers=self._graph_headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                status = str(item.get("fields", {}).get(SP_FIELD_STATUS, "")).strip().lower()
                if status == "pending":
                    all_pending.append(item)
            url = data.get("@odata.nextLink")
        return all_pending

    def update_item_status(self, item_id, status):
        """Update the Status column of a SharePoint list item."""
        site_id = self._discover_site()
        list_id = self._discover_list()
        url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
        resp = requests.patch(
            url, headers=self._graph_headers(),
            json={SP_FIELD_STATUS: status}, timeout=30
        )
        resp.raise_for_status()
        log.info(f"Item {item_id} status updated to '{status}'.")

    def list_item_fields(self, item_id):
        """Return raw fields dict for a single list item (discovery helper)."""
        site_id = self._discover_site()
        list_id = self._discover_list()
        url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}?$expand=fields"
        resp = requests.get(url, headers=self._graph_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("fields", {})

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

    def process_pending_items(self, crm_client):
        """Fetch Pending items and update the DRS Version on the CRM account."""
        items = self.get_pending_items()
        if not items:
            return 0

        log.info(f"Found {len(items)} pending item(s) to process.")
        processed = 0

        for item in items:
            item_id = item["id"]
            fields = item.get("fields", {})

            # Extract store number
            raw_store = fields.get(SP_FIELD_STORE_NUMBER, "")
            try:
                store_number = str(int(float(raw_store)))
            except (ValueError, TypeError):
                store_number = str(raw_store).strip()

            # Extract DRS version
            drs_version_label = str(fields.get(SP_FIELD_DRS_VERSION, "")).strip()

            if not store_number:
                log.warning(f"Item {item_id}: missing store number — skipping.")
                continue
            if not drs_version_label:
                log.warning(
                    f"Item {item_id} (store {store_number}): "
                    f"missing DRS version — skipping."
                )
                continue

            log.info(
                f"Processing item {item_id}: "
                f"store={store_number}, DRS version='{drs_version_label}'"
            )

            try:
                # Mark as Processing so we don't pick it up again on next poll
                self.update_item_status(item_id, "Processing")

                # Look up the CRM account by store number
                account = crm_client.lookup_account_by_store(store_number)
                account_id = account["accountid"]
                account_name = account.get("name", store_number)
                log.info(f"Found CRM account: {account_name} (ID: {account_id})")

                # Resolve the DRS version label to a CRM option code
                drs_version_code = self._resolve_drs_version(
                    drs_version_label, crm_client
                )
                log.info(
                    f"Resolved DRS version '{drs_version_label}' -> code {drs_version_code}"
                )

                # Update the DRS Version field on the account
                crm_client.update_account(
                    account_id,
                    **{CRM_DRS_VERSION_FIELD: drs_version_code}
                )
                log.info(
                    f"Store {store_number} ({account_name}): "
                    f"DRS Version updated to '{drs_version_label}'."
                )

                # Mark SharePoint item as Success
                self.update_item_status(item_id, "Success")
                processed += 1

            except Exception as e:
                log.error(
                    f"Failed to process item {item_id} "
                    f"(store {store_number}): {e}"
                )
                try:
                    self.update_item_status(item_id, "Failed")
                except Exception:
                    log.error(f"Could not update status for item {item_id}")

        return processed

    def run(self):
        """Main polling loop."""
        from crm_client import Dynamics365Client

        log.info("=" * 60)
        log.info("Splunk DRS Update → CRM DRS Version Poller starting")
        log.info(f"Poll interval: {POLL_INTERVAL}s")
        log.info(f"SharePoint list: {SHAREPOINT_LIST_NAME}")
        log.info(f"CRM DRS Version field: {CRM_DRS_VERSION_FIELD}")
        log.info("=" * 60)

        crm = Dynamics365Client()
        crm.authenticate()
        last_auth = time.time()

        # Discover SharePoint site/list and pre-load option map
        self._discover_site()
        self._discover_list()
        self._load_drs_option_map(crm)

        log.info("Ready. Polling for pending items...\n")

        while True:
            try:
                if time.time() - last_auth > 1800:
                    log.info("Re-authenticating CRM session...")
                    crm.authenticate()
                    last_auth = time.time()

                count = self.process_pending_items(crm)
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
        description="SharePoint 'Splunk DRS Update' → CRM DRS Version Poller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python drs_update_poller.py                        Start the continuous poller
  python drs_update_poller.py --once                 Run one cycle and exit
  python drs_update_poller.py --test-connection      Verify SP + CRM connections
  python drs_update_poller.py --discover-fields 1234 Inspect account fields for store 1234
  python drs_update_poller.py --list-drs-versions    List available DRS Version options in CRM
  python drs_update_poller.py --list-pending         Show current Pending items in SharePoint
        """,
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one poll cycle and exit")
    parser.add_argument("--interval", type=int, default=None,
                        help="Override poll interval in seconds")
    parser.add_argument("--test-connection", action="store_true",
                        help="Test SharePoint and CRM connections, then exit")
    parser.add_argument("--discover-fields", metavar="STORE_NUMBER",
                        help="Dump all CRM account fields for the given store number")
    parser.add_argument("--list-drs-versions", action="store_true",
                        help="List available DRS Version options from CRM metadata")
    parser.add_argument("--list-pending", action="store_true",
                        help="List current Pending items in the SharePoint list")
    args = parser.parse_args()

    if args.interval:
        POLL_INTERVAL = args.interval

    poller = DrsUpdatePoller()

    if args.test_connection:
        log.info("Testing SharePoint connection...")
        poller._discover_site()
        poller._discover_list()
        items = poller.get_pending_items()
        log.info(f"SharePoint OK. {len(items)} Pending item(s) found.")

        log.info("Testing CRM connection...")
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        log.info("CRM connection OK.")
        log.info("All connections verified!")

    elif args.discover_fields:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        account = crm.lookup_account_by_store(args.discover_fields)
        account_id = account["accountid"]
        log.info(
            f"Account: {account.get('name')} (store {args.discover_fields})\n"
            f"Fetching all fields..."
        )
        all_fields = crm.list_account_fields(account_id)
        # Filter to custom/win_ fields and non-null values for readability
        print("\n--- All non-null fields on this account ---")
        for k, v in sorted(all_fields.items()):
            if v is not None and not k.startswith("@"):
                print(f"  {k}: {v}")
        print("\n--- Fields with 'drs' in the name ---")
        for k, v in sorted(all_fields.items()):
            if "drs" in k.lower():
                print(f"  {k}: {v}")
        print(f"\nSet CRM_DRS_VERSION_FIELD=<field_name> in your .env once identified.")

    elif args.list_drs_versions:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        log.info(
            f"Fetching DRS Version options for field '{CRM_DRS_VERSION_FIELD}' "
            f"on 'account' entity..."
        )
        try:
            options = crm.get_option_set_values("account", CRM_DRS_VERSION_FIELD)
            print(f"\nAvailable DRS Version options ({len(options)}):")
            for label, code in sorted(options.items(), key=lambda x: x[1]):
                print(f"  [{code}] {label}")
        except Exception as e:
            print(f"Error: {e}")
            print(
                f"\nThe field '{CRM_DRS_VERSION_FIELD}' may not exist or may not be a "
                f"PickList type. Run --discover-fields <store> to find the correct field name."
            )

    elif args.list_pending:
        poller._discover_site()
        poller._discover_list()
        items = poller.get_pending_items()
        if not items:
            print("No Pending items found.")
        else:
            print(f"\n{len(items)} Pending item(s):\n")
            for item in items:
                f = item.get("fields", {})
                print(
                    f"  ID={item['id']}  "
                    f"Store={f.get(SP_FIELD_STORE_NUMBER, '?')}  "
                    f"DRS Version={f.get(SP_FIELD_DRS_VERSION, '?')}  "
                    f"Status={f.get(SP_FIELD_STATUS, '?')}"
                )

    elif args.once:
        from crm_client import Dynamics365Client
        crm = Dynamics365Client()
        crm.authenticate()
        poller._discover_site()
        poller._discover_list()
        count = poller.process_pending_items(crm)
        log.info(f"Done. Processed {count} DRS update(s).")

    else:
        poller.run()
