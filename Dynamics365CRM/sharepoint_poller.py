"""
SharePoint → Dynamics 365 CRM Case Creator
Polls a SharePoint list for approved items and creates CRM cases automatically.
"""

import os
import re
import sys
import time
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
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


class InvalidStoreNumberError(ValueError):
    """Raised when a store number is missing, malformed, or not found in CRM."""
    pass


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
            fields["ErrorMessage"] = str(error_msg)[:255]  # Limit length

        try:
            resp = requests.patch(
                url, headers=self._graph_headers(), json=fields, timeout=30
            )
            resp.raise_for_status()
            log.info(f"Item {item_id} status updated to '{status}'.")
        except requests.exceptions.HTTPError as e:
            # If ErrorMessage field doesn't exist, try without it
            if error_msg and e.response.status_code == 400:
                log.warning(f"Failed to update with error message, retrying without it...")
                fields = {"Status": status}
                resp = requests.patch(
                    url, headers=self._graph_headers(), json=fields, timeout=30
                )
                resp.raise_for_status()
                log.info(f"Item {item_id} status updated to '{status}' (without error message).")
            else:
                raise 

    # ─── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _utc_to_central(utc_dt):
        """Convert a naive UTC datetime to US Central (CDT/CST) naive datetime."""
        year = utc_dt.year
        mar_1 = datetime(year, 3, 1)
        cdt_start = mar_1 + timedelta(days=(6 - mar_1.weekday()) % 7 + 7)
        cdt_start = cdt_start.replace(hour=2)
        nov_1 = datetime(year, 11, 1)
        cst_start = nov_1 + timedelta(days=(6 - nov_1.weekday()) % 7)
        cst_start = cst_start.replace(hour=2)
        # Convert UTC to Central
        central_dt = utc_dt + timedelta(hours=-6)  # CST default
        if cdt_start <= central_dt.replace(tzinfo=None) < cst_start:
            central_dt = utc_dt + timedelta(hours=-5)  # CDT
        return central_dt

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

                # Strip any embedded HH:MM:SS timestamps (e.g. "05/13/2026 00:00:00" -> "05/13/2026")
                date_str = re.sub(r'\s+\d{1,2}:\d{2}:\d{2}\b', '', date_str).strip()

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

    def move_draft_to_shared(self, recipient_email, retry_delay=10):
        """
        Find a draft in the source mailbox addressed to recipient_email
        and move it to the Drafts folder of the shared mailbox.
        
        If no draft is found on first attempt, waits retry_delay seconds and tries once more.
        This handles cases where the draft is created shortly after the case.

        Returns the moved message ID, or None if no matching draft found.
        """
        headers = self._graph_headers()
        target_email = recipient_email.strip().lower()
        
        # Try up to 2 times: immediate, then after delay
        for attempt in range(2):
            matched_msg = None
            total_drafts_checked = 0

            # Paginate through drafts ordered by most recent first
            drafts_url = (
                f"{GRAPH_BASE}/users/{DRAFT_SOURCE_MAILBOX}/mailFolders/Drafts/messages"
                f"?$top=50&$select=id,subject,toRecipients,ccRecipients,bccRecipients,createdDateTime"
                f"&$orderby=createdDateTime desc"
            )
            while drafts_url and not matched_msg:
                resp = requests.get(drafts_url, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                drafts_in_batch = data.get("value", [])
                total_drafts_checked += len(drafts_in_batch)
                
                for msg in drafts_in_batch:
                    # Check To, CC, and BCC recipients
                    recipients = []
                    for field in ["toRecipients", "ccRecipients", "bccRecipients"]:
                        recipients.extend([
                            r["emailAddress"]["address"].lower()
                            for r in msg.get(field, [])
                            if r.get("emailAddress", {}).get("address")
                        ])
                    if target_email in recipients:
                        matched_msg = msg
                        break
                drafts_url = data.get("@odata.nextLink")

            if matched_msg:
                break  # Found it, proceed to move
            
            # If not found and this is first attempt, wait and retry
            if attempt == 0:
                log.info(
                    f"  Draft not found on first check (searched {total_drafts_checked} draft(s)). "
                    f"Waiting {retry_delay} seconds for draft to be created..."
                )
                time.sleep(retry_delay)
                log.info(f"  Retrying draft search for '{recipient_email}'...")
            else:
                # Second attempt failed
                log.warning(
                    f"  No draft found in {DRAFT_SOURCE_MAILBOX} "
                    f"addressed to '{recipient_email}' after retry. Searched {total_drafts_checked} draft(s)."
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

    def _search_email_in_folders(self, folders, check_sender, email_address, start_time, end_time,
                                  parent_folder, parent_location, headers):
        """
        Search for an email in the given folders within a time window.
        
        Returns:
            dict with 'folder_name', 'msg_id', 'msg_time', 'msg_from', 'match_count' if found, else None
        """
        for folder_name in folders:
            folder_id = None
            
            # Check if this folder has a nested parent (e.g., Splunk Alerts inside INTERNAL REQUESTS)
            if parent_location and parent_folder:
                parent_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{parent_location}/childFolders"
                parent_id = None
                
                while parent_url and not parent_id:
                    parent_resp = requests.get(parent_url, headers=headers, timeout=30)
                    parent_resp.raise_for_status()
                    
                    for f in parent_resp.json().get("value", []):
                        if f.get("displayName") == parent_folder:
                            parent_id = f["id"]
                            break
                    
                    parent_url = parent_resp.json().get("@odata.nextLink")
                
                if not parent_id:
                    continue
                
                target_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{parent_id}/childFolders"
                target_resp = requests.get(target_url, headers=headers, timeout=30)
                target_resp.raise_for_status()
                
                for f in target_resp.json().get("value", []):
                    if f.get("displayName") == folder_name:
                        folder_id = f["id"]
                        break
            
            elif parent_folder:
                search_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{parent_folder}/childFolders"
                
                while search_url and not folder_id:
                    search_resp = requests.get(search_url, headers=headers, timeout=30)
                    search_resp.raise_for_status()
                    
                    for f in search_resp.json().get("value", []):
                        if f.get("displayName") == folder_name:
                            folder_id = f["id"]
                            break
                    
                    search_url = search_resp.json().get("@odata.nextLink")
            
            else:
                search_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders"
                
                while search_url and not folder_id:
                    search_resp = requests.get(search_url, headers=headers, timeout=30)
                    search_resp.raise_for_status()
                    
                    for f in search_resp.json().get("value", []):
                        if f.get("displayName") == folder_name:
                            folder_id = f["id"]
                            break
                    
                    search_url = search_resp.json().get("@odata.nextLink")
            
            if not folder_id:
                continue
            
            # Search for emails in time window (time filter only — Graph API does not
            # reliably support from/emailAddress/address as a $filter property, so we
            # apply sender filtering client-side after fetching results)
            filter_query = f"receivedDateTime ge {start_time} and receivedDateTime le {end_time}"
            
            messages_url = (
                f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{folder_id}/messages"
                f"?$filter={filter_query}"
                f"&$select=id,subject,receivedDateTime,from"
                f"&$top=20"
            )
            
            msg_resp = requests.get(messages_url, headers=headers, timeout=30)
            msg_resp.raise_for_status()
            messages = msg_resp.json().get("value", [])
            
            # Client-side sender filter (more reliable than Graph API $filter on from)
            if check_sender and email_address:
                expected = email_address.lower()
                messages = [
                    m for m in messages
                    if m.get("from", {}).get("emailAddress", {}).get("address", "").lower() == expected
                ]
            
            if messages:
                msg = messages[0]
                return {
                    "folder_name": folder_name,
                    "msg_id": msg.get("id", ""),
                    "msg_time": msg.get("receivedDateTime", ""),
                    "msg_from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "match_count": len(messages),
                }
        
        return None

    def _search_subfolder(self, folder_path, start_time, end_time, check_sender, email_address, headers):
        """
        Search messages in a folder identified by a display-name path from the mailbox root.
        e.g. folder_path=["Create CRM Case", "Retry"] navigates root -> Create CRM Case -> Retry.
        Returns the same dict shape as _search_email_in_folders, or None.
        """
        current_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders"
        folder_id = None

        for name in folder_path:
            found_id = None
            page_url = current_url
            while page_url:
                resp = requests.get(page_url, headers=headers, timeout=30)
                resp.raise_for_status()
                for f in resp.json().get("value", []):
                    if f.get("displayName") == name:
                        found_id = f["id"]
                        break
                if found_id:
                    break
                page_url = resp.json().get("@odata.nextLink")
            if not found_id:
                return None
            folder_id = found_id
            current_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{folder_id}/childFolders"

        if not folder_id:
            return None

        filter_query = f"receivedDateTime ge {start_time} and receivedDateTime le {end_time}"
        messages_url = (
            f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/mailFolders/{folder_id}/messages"
            f"?$filter={filter_query}"
            f"&$select=id,subject,receivedDateTime,from"
            f"&$top=20"
        )
        msg_resp = requests.get(messages_url, headers=headers, timeout=30)
        msg_resp.raise_for_status()
        messages = msg_resp.json().get("value", [])

        if check_sender and email_address:
            expected = email_address.lower()
            messages = [
                m for m in messages
                if m.get("from", {}).get("emailAddress", {}).get("address", "").lower() == expected
            ]

        if messages:
            msg = messages[0]
            return {
                "folder_name": "/".join(folder_path),
                "msg_id": msg.get("id", ""),
                "msg_time": msg.get("receivedDateTime", ""),
                "msg_from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "match_count": len(messages),
            }
        return None

    def _maybe_narrow_result(self, result, config_key, base_dt, folders, check_sender,
                              email_address, parent_folder, parent_location, headers):
        """If multiple emails found for a time-only origin, narrow the window to ±1 min."""
        if config_key in {"voice_to_text", "internal", "splunk"} and result.get("match_count", 1) > 1:
            log.info(
                f"  [Email Verification] {result['match_count']} emails in ±2 min window, "
                f"narrowing to ±1 min..."
            )
            narrow_start = (base_dt - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            narrow_end   = (base_dt + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            narrow_result = self._search_email_in_folders(
                folders, check_sender, email_address, narrow_start, narrow_end,
                parent_folder, parent_location, headers
            )
            if narrow_result:
                return narrow_result
            log.info(f"  [Email Verification] No unique match at ±1 min, keeping ±2 min result.")
        return result

    def _move_email_to_inbox(self, msg_id):
        """Move an email in the shared mailbox to the Inbox and mark it as unread."""
        headers = self._graph_headers()
        base_url = f"{GRAPH_BASE}/users/{DRAFT_TARGET_MAILBOX}/messages"
        try:
            move_resp = requests.post(
                f"{base_url}/{msg_id}/move",
                headers=headers,
                json={"destinationId": "inbox"},
                timeout=30,
            )
            move_resp.raise_for_status()
            new_id = move_resp.json().get("id", msg_id)
            log.info(f"  [Email] Moved email to Inbox.")
            unread_resp = requests.patch(
                f"{base_url}/{new_id}",
                headers=headers,
                json={"isRead": False},
                timeout=30,
            )
            unread_resp.raise_for_status()
            log.info(f"  [Email] Marked email as unread.")
            return True
        except Exception as e:
            log.warning(f"  [Email] Failed to move/unread email: {e}")
            return False

    def verify_email_in_folder(self, origin_text, email_address, received_datetime_str, store_number, item_id=None):
        """
        Verify that an email exists in the appropriate folder based on origin.
        
        If not found at the original time, tries ±12h (AM/PM swap) and ±24h (wrong date)
        offsets. If found with an offset, returns the corrected datetime so the caller
        can update SharePoint and CRM.
        
        Returns:
            dict  – {"found": True, "corrected_datetime": <str or None>, "folder": ..., "msg_time": ..., "msg_from": ...}
                     corrected_datetime is None if found at original time, or ISO string if found at offset
            dict  – {"found": False} if not found at all
        """
        # Load configuration from JSON file
        config_path = os.path.join(os.path.dirname(__file__), "email_verification_config.json")
        try:
            with open(config_path, 'r') as f:
                folder_config = json.load(f)
        except Exception as e:
            log.error(f"  [Email Verification] Failed to load config file: {e}")
            return {"found": True, "corrected_datetime": None}
        
        # Map SharePoint origin text to config key
        origin_lower = origin_text.lower()
        
        if "voice to text" in origin_lower or "phone" in origin_lower:
            config_key = "voice_to_text"
        elif "email" in origin_lower:
            config_key = "email"
        elif "web" in origin_lower:
            config_key = "web"
        elif "splunk" in origin_lower:
            config_key = "splunk"
        elif "internal" in origin_lower:
            config_key = "internal"
        else:
            log.warning(f"  [Email Verification] Unknown origin '{origin_text}', skipping verification")
            return {"found": True, "corrected_datetime": None}
        
        # Get folder configuration
        origin_config = folder_config.get(config_key, {})
        folders = origin_config.get("folders", [])
        
        # Skip if no folders configured (e.g., Web)
        if not folders:
            return {"found": True, "corrected_datetime": None}
        
        folder = folders if len(folders) > 1 else folders[0] if folders else None
        check_sender = origin_config.get("check_sender", False)
        parent_folder = origin_config.get("parent_folder")
        parent_location = origin_config.get("parent_location")
        
        try:
            # Parse received datetime
            received_dt = datetime.strptime(received_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
            
            # Search window: ±2 minutes
            start_time = (received_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            end_time = (received_dt + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            headers = self._graph_headers()
            folders = folder if isinstance(folder, list) else [folder]
            
            # Always include "Create CRM Case" in every search attempt
            if "Create CRM Case" not in folders:
                folders = folders + ["Create CRM Case"]
            
            # Try up to 2 times: immediate, then after 10 seconds
            for attempt in range(2):
                result = self._search_email_in_folders(
                    folders, check_sender, email_address, start_time, end_time,
                    parent_folder, parent_location, headers
                )

                # Also search Create CRM Case/Retry and Create CRM Case/Retry 2
                # (email may have been staged there by the folder monitor)
                if not result:
                    result = self._search_subfolder(
                        ["Create CRM Case", "Retry"],
                        start_time, end_time,
                        check_sender, email_address, headers
                    )
                if not result:
                    result = self._search_subfolder(
                        ["Create CRM Case", "Retry 2"],
                        start_time, end_time,
                        check_sender, email_address, headers
                    )
                
                if result:
                    result = self._maybe_narrow_result(
                        result, config_key, received_dt, folders, check_sender,
                        email_address, parent_folder, parent_location, headers
                    )
                    log.info(f"  [Email Verification] [OK] Found email in '{result['folder_name']}' at {result['msg_time']} from {result['msg_from']}")
                    
                    # Update SharePoint EmailVerification column to Yes
                    if item_id:
                        try:
                            self.update_item_fields(item_id, EmailVerification=True)
                        except Exception as e:
                            log.warning(f"  Failed to update EmailVerification column: {e}")
                    
                    return {"found": True, "corrected_datetime": None, "msg_id": result.get("msg_id", ""),
                            "folder": result["folder_name"], "msg_time": result["msg_time"], "msg_from": result["msg_from"]}
                
                # If not found and this is first attempt, wait and retry
                if attempt == 0:
                    log.info(f"  [Email Verification] Email not found on first check. Waiting 10 seconds for email to be moved...")
                    time.sleep(10)
                    log.info(f"  [Email Verification] Retrying email search in {folders}...")
            
            # ── Time-correction search: try ±12h and ±24h offsets ──
            # This handles AI errors: wrong AM/PM (±12h) or wrong date (±24h)
            offsets = [
                (timedelta(hours=-12), "-12h (AM/PM swap)"),
                (timedelta(hours=12),  "+12h (AM/PM swap)"),
                (timedelta(hours=-24), "-24h (wrong date)"),
                (timedelta(hours=24),  "+24h (wrong date)"),
            ]
            
            log.info(f"  [Email Verification] Trying time-corrected search (+/-12h, +/-24h)...")
            
            for offset, offset_label in offsets:
                corrected_dt = received_dt + offset
                corr_start = (corrected_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
                corr_end = (corrected_dt + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
                
                result = self._search_email_in_folders(
                    folders, check_sender, email_address, corr_start, corr_end,
                    parent_folder, parent_location, headers
                )
                
                if result:
                    result = self._maybe_narrow_result(
                        result, config_key, corrected_dt, folders, check_sender,
                        email_address, parent_folder, parent_location, headers
                    )
                    corrected_iso = corrected_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    log.info(
                        f"  [Email Verification] [OK] Found email with {offset_label} correction "
                        f"in '{result['folder_name']}' at {result['msg_time']} from {result['msg_from']}"
                    )
                    log.info(f"  [Email Verification] Correcting received time from {received_datetime_str} to {corrected_iso}")
                    
                    # Update SharePoint EmailVerification column to Yes
                    if item_id:
                        try:
                            self.update_item_fields(item_id, EmailVerification=True)
                        except Exception as e:
                            log.warning(f"  Failed to update EmailVerification column: {e}")
                    
                    return {"found": True, "corrected_datetime": corrected_iso, "msg_id": result.get("msg_id", ""),
                            "folder": result["folder_name"], "msg_time": result["msg_time"], "msg_from": result["msg_from"]}
            
            # Not found at any offset
            log.warning(f"  [Email Verification] [NOT FOUND] No email found in {folders} within +/-2 minutes of {received_datetime_str} or +/-12h/24h offsets")
            if check_sender:
                log.warning(f"  [Email Verification] Expected sender: {email_address}")
            
            # Update SharePoint EmailVerification column to No
            if item_id:
                try:
                    self.update_item_fields(item_id, EmailVerification=False)
                except Exception as e:
                    log.warning(f"  Failed to update EmailVerification column: {e}")
            
            return {"found": False}
            
        except Exception as e:
            log.error(f"  [Email Verification] Error during verification: {e}")
            return {"found": False}

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

            ev_result = None
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

                # Validate required fields before proceeding
                store_num = case_params.get('store_number', '').strip()
                if not store_num or store_num == '?':
                    raise InvalidStoreNumberError(f"Invalid or missing store number: '{raw_store}'")
                
                subject = case_params.get('subject', '').strip()
                if not subject:
                    raise ValueError("Subject is required but was not provided")
                
                # Validate subject exists in CRM
                try:
                    subject_code = crm_client.resolve_subject(subject)
                except ValueError as e:
                    raise ValueError(f"Invalid subject '{subject}': {e}")
                
                # Validate received_on format and check for future dates
                received_on = case_params.get('received_on')
                received_on_utc = None
                if received_on:
                    try:
                        received_on_utc = crm_client.parse_received_on(received_on)
                        received_dt = datetime.strptime(received_on_utc, "%Y-%m-%dT%H:%M:%SZ")
                        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                        
                        # Check if received time is in the future (warning only, don't block)
                        if received_dt > now_utc:
                            time_in_future = received_dt - now_utc
                            log.warning(
                                f"  [TIME WARNING] Received-on time '{received_on}' is in the future by {time_in_future}. "
                                f"This is likely an AI extraction error."
                            )
                    except ValueError as e:
                        raise ValueError(f"Invalid received-on date/time '{received_on}': {e}")

                # Email verification BEFORE case creation — so time corrections
                # happen first and the case gets created with the right time
                if received_on_utc:
                    origin_text = str(fields.get('Origin', '')).strip()
                    email_addr = str(fields.get('emailaddress', '')).strip()
                    ev_result = self.verify_email_in_folder(
                        origin_text, email_addr, received_on_utc,
                        case_params['store_number'], item_id
                    )
                    
                    # If email was found with a time correction, fix received_on before case creation
                    if ev_result.get("corrected_datetime"):
                        corrected_iso = ev_result["corrected_datetime"]
                        corrected_utc_dt = datetime.strptime(corrected_iso, "%Y-%m-%dT%H:%M:%SZ")
                        local_dt = self._utc_to_central(corrected_utc_dt)
                        corrected_date = local_dt.strftime("%m/%d/%Y")
                        corrected_time = local_dt.strftime("%I:%M %p").lstrip("0").lower()
                        corrected_local = f"{corrected_date} {corrected_time}"
                        
                        # Update case_params so case gets created with correct time
                        case_params['received_on'] = corrected_local
                        received_on_utc = corrected_iso
                        log.info(f"  [Time Correction] Corrected received_on to {corrected_local} (UTC: {corrected_iso})")
                        
                        # Update SharePoint columns
                        try:
                            self.update_item_fields(item_id, Dateandtime=corrected_date, Time=corrected_time)
                            log.info(f"  [Time Correction] Updated SharePoint: Dateandtime={corrected_date}, Time={corrected_time}")
                        except Exception as e:
                            log.warning(f"  [Time Correction] Failed to update SharePoint columns: {e}")

                # Duplicate Detection: Check if case created today within 5 minutes
                existing = None
                dup_reason = None
                is_exact_duplicate = False
                
                same_day_case = crm_client.find_active_case_today(case_params["store_number"])
                if same_day_case:
                    # Check if received-on times are within 5 minutes
                    new_received_on_raw = case_params.get("received_on", "")
                    existing_received_on = same_day_case.get("received_on", "")
                    if new_received_on_raw and existing_received_on:
                        try:
                            # Convert new received-on to UTC (same as CRM stores it)
                            new_received_utc = crm_client.parse_received_on(new_received_on_raw)
                            new_dt = datetime.strptime(new_received_utc, "%Y-%m-%dT%H:%M:%SZ")
                            ext_dt = datetime.strptime(existing_received_on, "%Y-%m-%dT%H:%M:%SZ")
                            time_diff = abs(new_dt - ext_dt)
                            log.info(f"  Time comparison: new={new_received_utc} existing={existing_received_on} diff={time_diff}")
                            if time_diff <= timedelta(minutes=5):
                                is_exact_duplicate = True
                                existing = same_day_case
                                dup_reason = "duplicate (within 5 min)"
                        except ValueError as e:
                            log.warning(f"  Could not compare received-on times: {e}")
                
                # Check 1: active case for same store with same subject (any date)
                if not existing and subject_code is not None:
                    existing = crm_client.find_active_case_by_subject(
                        case_params["store_number"], subject_code
                    )
                    dup_reason = "same-subject"

                if not existing:
                    # Check 2: resolved case for same store, same day, same subject
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
                                # Use case_params received_on (already corrected if time correction happened)
                                dt_label = ""
                                ro = case_params.get('received_on', '')
                                if ro:
                                    dt_label = f" {ro}"
                                else:
                                    # Fallback to SharePoint columns
                                    note_date = str(fields.get("Dateandtime", "")).strip()
                                    note_time = str(fields.get("Time", "")).strip()
                                    if note_date and "T" in note_date:
                                        dt = datetime.fromisoformat(note_date.replace("Z", ""))
                                        note_date = dt.strftime("%m/%d/%Y")
                                    note_date = re.sub(r'\s+\d{1,2}:\d{2}:\d{2}\b', '', note_date).strip()
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

                        # Move draft reply for increments only
                        draft_reply = fields.get("DraftReply", False)
                        if draft_reply:
                            recipient_email = str(fields.get("emailaddress", "")).strip()
                            if recipient_email:
                                try:
                                    self.move_draft_to_shared(recipient_email)
                                except Exception as e:
                                    log.warning(f"  Failed to move draft: {e}")

                    # Move draft reply for duplicates (without adding note)
                    if is_exact_duplicate:
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
                try:
                    result = crm_client.create_case(**case_params)
                except ValueError as e:
                    if "No account found for store number" in str(e) or "is inactive/closed" in str(e):
                        raise InvalidStoreNumberError(str(e))
                    raise

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
                
                # Log case creation with time details
                case_id = result.get('case_id', '?')
                ticket_number = result.get('ticketnumber', '?')
                createdon = result.get('createdon', '')
                receivedon = result.get('win_receivedon', '')
                
                log.info(f"Case created for store {case_params['store_number']}: {ticket_number} (ID: {case_id})")
                
                # Calculate and log time difference
                if createdon and receivedon:
                    try:
                        created_dt = datetime.strptime(createdon, "%Y-%m-%dT%H:%M:%SZ")
                        received_dt = datetime.strptime(receivedon, "%Y-%m-%dT%H:%M:%SZ")
                        time_diff = created_dt - received_dt
                        
                        # Format times for logging
                        log.info(f"  Received On: {receivedon}")
                        log.info(f"  Created On:  {createdon}")
                        
                        # Check for anomalies: negative time or >= 8 hours
                        total_seconds = abs(time_diff.total_seconds())
                        hours_diff = total_seconds / 3600
                        
                        if time_diff.total_seconds() < 0:
                            # Negative time difference (received after created)
                            log.error(f"  \033[91m[RED FLAG] Time Difference: {time_diff} (Created - Received) - NEGATIVE TIME DIFFERENCE!\033[0m")
                            log.error(f"  \033[91m[RED FLAG] Case was received AFTER it was created. This indicates a data error.\033[0m")
                        elif hours_diff >= 8:
                            # 8+ hour difference
                            log.error(f"  \033[91m[RED FLAG] Time Difference: {time_diff} (Created - Received) - {hours_diff:.1f} HOURS!\033[0m")
                            log.error(f"  \033[91m[RED FLAG] Time difference exceeds 8 hours. This may indicate an AI extraction error.\033[0m")
                        else:
                            # Normal time difference
                            log.info(f"  Time Difference: {time_diff} (Created - Received)")
                    except ValueError as e:
                        log.warning(f"  Could not calculate time difference: {e}")
                else:
                    log.info(f"  Received On: {receivedon if receivedon else 'N/A'}")
                    log.info(f"  Created On:  {createdon if createdon else 'N/A'}")
                
                processed += 1

            except InvalidStoreNumberError as e:
                log.error(f"Invalid store number for item {item_id} (store {store}): {e}")
                try:
                    self.update_item_status(item_id, "Invalid Store Number", str(e))
                    log.info(f"  Item {item_id} marked as Invalid Store Number: {e}")
                except Exception as update_err:
                    log.error(f"Could not update status for item {item_id}: {update_err}")
                if ev_result and ev_result.get("msg_id"):
                    log.info(f"  [Email] Moving verified email back to Inbox and marking unread...")
                    self._move_email_to_inbox(ev_result["msg_id"])
            except ValueError as e:
                # Validation errors - log and mark as Failed with clear error message
                log.error(f"Validation error for item {item_id} (store {store}): {e}")
                try:
                    error_msg = str(e)
                    self.update_item_status(item_id, "Failed", error_msg)
                    log.info(f"  Item {item_id} marked as Failed: {error_msg}")
                except Exception as update_err:
                    log.error(f"Could not update status for item {item_id}: {update_err}")
                if ev_result and ev_result.get("msg_id"):
                    log.info(f"  [Email] Moving verified email back to Inbox and marking unread...")
                    self._move_email_to_inbox(ev_result["msg_id"])
            except Exception as e:
                # Other errors (network, CRM issues, etc.)
                log.error(f"Failed to process item {item_id} (store {store}): {e}")
                try:
                    error_msg = f"Error: {type(e).__name__}: {str(e)}"
                    self.update_item_status(item_id, "Failed", error_msg)
                    log.info(f"  Item {item_id} marked as Failed")
                except Exception as update_err:
                    log.error(f"Could not update status for item {item_id}: {update_err}")
                if ev_result and ev_result.get("msg_id"):
                    log.info(f"  [Email] Moving verified email back to Inbox and marking unread...")
                    self._move_email_to_inbox(ev_result["msg_id"])

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
