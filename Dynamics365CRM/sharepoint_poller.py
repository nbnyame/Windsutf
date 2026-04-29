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
from datetime import datetime, timedelta
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

# Draft email settings
DRAFT_SOURCE_MAILBOX = os.getenv("DRAFT_SOURCE_MAILBOX", "nnyamekye@winmarkcorporation.com")
DRAFT_TARGET_MAILBOX = os.getenv("DRAFT_TARGET_MAILBOX", "supportcenter@winmarkcorporation.com")

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
        all_lists = []
        while url:
            resp = requests.get(url, headers=self._graph_headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            page_lists = data.get("value", [])
            all_lists.extend(page_lists)
            for lst in page_lists:
                if lst["displayName"].lower() == SHAREPOINT_LIST_NAME.lower():
                    self.list_id = lst["id"]
                    log.info(f"SharePoint list '{SHAREPOINT_LIST_NAME}' ID: {self.list_id}")
                    return self.list_id
            url = data.get("@odata.nextLink")

        raise ValueError(
            f"List '{SHAREPOINT_LIST_NAME}' not found. "
            f"Available: {[l['displayName'] for l in all_lists]}"
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

    def update_item_fields(self, item_id, **field_values):
        """Update arbitrary fields on a SharePoint list item."""
        site_id = self._discover_site()
        list_id = self._discover_list()
        url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
        resp = requests.patch(url, headers=self._graph_headers(),
                              json=field_values, timeout=30)
        resp.raise_for_status()

    def update_item_status(self, item_id, status, error_msg=None):
        """Update the Status column of a SharePoint list item."""
        site_id = self._discover_site()
        list_id = self._discover_list()

        url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
        fields = {"Status": status}
        if error_msg:
            fields["ErrorMessage"] = str(error_msg)

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

    # ─── Draft Email Management ─────────────────────────────────────────

    def move_draft_to_shared(self, recipient_email):
        """
        Find a draft in the source mailbox addressed to recipient_email
        and move it to the Drafts folder of the shared mailbox.

        Returns the moved message ID, or None if no matching draft found.
        """
        headers = self._graph_headers()

        target_email = recipient_email.strip().lower()
        matched_msg = None

        # Paginate through drafts ordered by most recent first
        drafts_url = (
            f"{GRAPH_BASE}/users/{DRAFT_SOURCE_MAILBOX}/mailFolders/Drafts/messages"
            f"?$top=50&$select=id,subject,toRecipients,createdDateTime"
            f"&$orderby=createdDateTime desc"
        )
        while drafts_url and not matched_msg:
            resp = requests.get(drafts_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for msg in data.get("value", []):
                recipients = [
                    r["emailAddress"]["address"].lower()
                    for r in msg.get("toRecipients", [])
                    if r.get("emailAddress", {}).get("address")
                ]
                if target_email in recipients:
                    matched_msg = msg
                    break
            drafts_url = data.get("@odata.nextLink")

        if not matched_msg:
            log.warning(
                f"  No draft found in {DRAFT_SOURCE_MAILBOX} "
                f"addressed to '{recipient_email}'."
            )
            return None

        msg_id = matched_msg["id"]
        log.info(
            f"  Found draft: '{matched_msg.get('subject', '?')}' "
            f"-> moving to {DRAFT_TARGET_MAILBOX} Drafts"
        )

        # Get the Drafts folder ID of the shared mailbox
        folder_resp = requests.get(
            f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/Drafts"
            f"?$select=id",
            headers=headers, timeout=30,
        )
        folder_resp.raise_for_status()
        target_folder_id = folder_resp.json()["id"]

        # Copy the draft to the shared mailbox Drafts folder
        # (Graph API cannot move across mailboxes, so we copy then delete)

        # Step 1: Read the full draft message
        full_msg_resp = requests.get(
            f"{GRAPH_BASE}/users/{DRAFT_SOURCE_MAILBOX}/messages/{msg_id}"
            f"?$select=subject,body,toRecipients,ccRecipients,bccRecipients,"
            f"from,replyTo,importance,categories",
            headers=headers, timeout=30,
        )
        full_msg_resp.raise_for_status()
        original = full_msg_resp.json()

        # Step 2: Create the draft in the shared mailbox Drafts folder
        new_draft = {
            "subject": original.get("subject", ""),
            "body": original.get("body", {}),
            "toRecipients": original.get("toRecipients", []),
            "ccRecipients": original.get("ccRecipients", []),
            "bccRecipients": original.get("bccRecipients", []),
            "importance": original.get("importance", "normal"),
            "from": {
                "emailAddress": {
                    "address": DRAFT_TARGET_MAILBOX,
                    "name": "Winmark Support Center",
                }
            },
        }

        create_resp = requests.post(
            f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{target_folder_id}/messages",
            headers=headers, json=new_draft, timeout=30,
        )
        create_resp.raise_for_status()
        new_msg_id = create_resp.json().get("id", "?")

        # Step 3: Delete the original draft from personal mailbox
        del_resp = requests.delete(
            f"{GRAPH_BASE}/users/{DRAFT_SOURCE_MAILBOX}/messages/{msg_id}",
            headers=headers, timeout=30,
        )
        if del_resp.status_code in (200, 204):
            log.info(f"  Draft moved successfully (new ID: {new_msg_id[:20]}...)")
        else:
            log.warning(f"  Draft copied but failed to delete original: {del_resp.status_code}")

        return new_msg_id

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
                log.info(f"Processing store {case_params['store_number']}...")
                log.info(f"  Params: contact={case_params.get('contact')}, "
                         f"phone={case_params.get('contact_phone')}, "
                         f"subject={case_params.get('subject')}, "
                         f"case_type={case_params.get('case_type')}")

                # Check 1: active case for same store created today
                existing = crm_client.find_active_case_today(case_params["store_number"])
                dup_reason = "same-day"
                is_exact_duplicate = False
                subject_code = None

                if existing:
                    # Check if received-on times are within 5 minutes
                    new_received_on_raw = case_params.get("received_on", "")
                    existing_received_on = existing.get("received_on", "")
                    if new_received_on_raw and existing_received_on:
                        try:
                            # Convert new received-on to UTC (same as CRM stores it)
                            new_received_utc = crm_client.parse_received_on(new_received_on_raw)
                            new_dt = datetime.strptime(new_received_utc, "%Y-%m-%dT%H:%M:%SZ")
                            ext_dt = datetime.strptime(existing_received_on, "%Y-%m-%dT%H:%M:%SZ")
                            log.info(f"  Time comparison: new={new_received_utc} existing={existing_received_on} diff={abs(new_dt - ext_dt)}")
                            if abs(new_dt - ext_dt) <= timedelta(minutes=5):
                                is_exact_duplicate = True
                                dup_reason = "duplicate (within 5 min)"
                        except ValueError as e:
                            log.warning(f"  Could not compare received-on times: {e}")

                if not existing:
                    # Check 2: active case for same store with same subject (any date)
                    subject_code = crm_client.resolve_subject(case_params.get("subject", ""))
                    if subject_code is not None:
                        existing = crm_client.find_active_case_by_subject(
                            case_params["store_number"], subject_code
                        )
                        dup_reason = "same-subject"

                if not existing:
                    # Check 3: resolved case for same store, same day, same subject
                    if subject_code is None:
                        subject_code = crm_client.resolve_subject(case_params.get("subject", ""))
                    if subject_code is not None:
                        existing = crm_client.find_resolved_case_today_by_subject(
                            case_params["store_number"], subject_code
                        )
                        dup_reason = "resolved-same-day-subject"

                if existing:
                    if is_exact_duplicate:
                        # Exact duplicate — mark Duplicate, no notes
                        log.info(
                            f"  Exact duplicate ({dup_reason}): {existing['ticketnumber']} "
                            f"(owner: {existing['owner_name']}). Skipping case creation."
                        )
                        self.update_item_fields(
                            item_id,
                            Duplicate=True,
                            Incrementperson=existing["owner_name"],
                        )
                    else:
                        # Increment — add note to existing case
                        log.info(
                            f"  Increment ({dup_reason}): {existing['ticketnumber']} "
                            f"(owner: {existing['owner_name']}). Skipping case creation."
                        )
                        self.update_item_fields(
                            item_id,
                            Increment=True,
                            Incrementperson=existing["owner_name"],
                        )
                        # Add Full Message as note on the existing case
                        full_message = str(fields.get("FullMessage", "")).strip()
                        if full_message and existing.get("case_id"):
                            try:
                                # Build date/time string from SharePoint columns
                                note_date = str(fields.get("Dateandtime", "")).strip()
                                note_time = str(fields.get("Time", "")).strip()
                                if note_date and "T" in note_date:
                                    dt = datetime.fromisoformat(note_date.replace("Z", ""))
                                    note_date = dt.strftime("%m/%d/%Y")
                                if note_time:
                                    time_match = re.match(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', note_time)
                                    if time_match:
                                        note_time = time_match.group(1)
                                dt_label = f" {note_date}"
                                if note_time:
                                    dt_label += f" {note_time}"
                                note_subject = f"Increment{dt_label}"

                                crm_client.create_note(
                                    existing["case_id"],
                                    text=full_message,
                                    subject=note_subject,
                                )
                                log.info(f"  Increment note added to {existing['ticketnumber']}.")
                            except Exception as e:
                                log.warning(f"  Failed to add increment note: {e}")

                    # Move draft reply for both duplicates and increments
                    draft_reply = fields.get("DraftReply", False)
                    if draft_reply:
                        recipient_email = str(fields.get("emailaddress", "")).strip()
                        if recipient_email:
                            try:
                                self.move_draft_to_shared(recipient_email)
                            except Exception as e:
                                log.warning(f"  Failed to move draft: {e}")

                    self.update_item_status(item_id, "Processed")
                    log.info(f"  Item {item_id} marked as Processed ({dup_reason}).")
                    processed += 1
                    continue

                # No duplicate — create the case
                log.info(f"  No duplicate found. Creating case...")
                result = crm_client.create_case(**case_params)

                # Add note from Full Message column if present
                full_message = str(fields.get("FullMessage", "")).strip()
                if full_message and result.get("case_id"):
                    try:
                        crm_client.create_note(
                            result["case_id"],
                            text=full_message,
                            subject="Full Message",
                        )
                        log.info(f"  Note added to case.")
                    except Exception as e:
                        log.warning(f"  Failed to add note: {e}")

                # Move draft reply to shared mailbox if DraftReply is True
                draft_reply = fields.get("DraftReply", False)
                if draft_reply:
                    recipient_email = str(fields.get("emailaddress", "")).strip()
                    if recipient_email:
                        try:
                            self.move_draft_to_shared(recipient_email)
                        except Exception as e:
                            log.warning(f"  Failed to move draft: {e}")
                    else:
                        log.warning(f"  DraftReply=True but no email address on item.")

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
