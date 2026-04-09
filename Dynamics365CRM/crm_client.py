"""
Dynamics 365 CRM Client
Handles authentication and API calls to Microsoft Dynamics 365.
"""

import os
import re
import json
import requests
from datetime import datetime
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser
from dotenv import load_dotenv

load_dotenv()


class Dynamics365Client:
    """Client for interacting with Microsoft Dynamics 365 CRM Web API."""

    def __init__(self):
        self.crm_url = os.getenv("CRM_URL", "").rstrip("/")
        self.domain = os.getenv("CRM_DOMAIN", "")
        self.username = os.getenv("CRM_USERNAME", "")
        self.password = os.getenv("CRM_PASSWORD", "")
        self.api_base = f"{self.crm_url}/api/data/v8.2"
        self.session = None

        if not all([self.crm_url, self.domain, self.username, self.password]):
            raise ValueError(
                "Missing CRM credentials. Please set CRM_URL, CRM_DOMAIN, "
                "CRM_USERNAME, and CRM_PASSWORD in your .env file."
            )

    @staticmethod
    def _parse_form(html):
        """Extract form action URL and hidden input fields from HTML."""
        class FormParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.action = None
                self.fields = {}
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "form" and self.action is None:
                    self.action = attrs_dict.get("action", "")
                if tag == "input" and attrs_dict.get("type", "").lower() == "hidden":
                    name = attrs_dict.get("name", "")
                    value = attrs_dict.get("value", "")
                    if name:
                        self.fields[name] = value
        parser = FormParser()
        parser.feed(html)
        return parser.action, parser.fields

    def authenticate(self):
        """Authenticate with on-premises Dynamics 365 via ADFS WS-Federation."""
        self.session = requests.Session()
        self.session.verify = True

        # Step 1: Hit the CRM URL — this redirects to the ADFS login page
        print("Connecting to CRM...")
        r1 = self.session.get(self.crm_url, timeout=30, allow_redirects=True)

        if r1.status_code != 200:
            raise ConnectionError(
                f"Failed to reach CRM/ADFS: HTTP {r1.status_code}"
            )

        # Step 2: Parse the ADFS login form
        adfs_url = r1.url  # The final URL after redirects (ADFS login page)
        form_action, form_fields = self._parse_form(r1.text)

        if not form_action:
            raise ConnectionError(
                "Could not find ADFS login form. The CRM may use a different auth method."
            )

        # Resolve relative form action URL
        if not form_action.startswith("http"):
            parsed = urlparse(adfs_url)
            form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"

        # Step 3: Submit credentials to ADFS
        login_user = f"{self.domain}\\{self.username}"
        form_fields["UserName"] = login_user
        form_fields["Password"] = self.password

        print(f"Authenticating as {login_user} via ADFS...")
        r2 = self.session.post(
            form_action, data=form_fields, timeout=30, allow_redirects=False,
        )

        # Step 4: ADFS returns a page with a SAML token form that auto-submits to CRM
        # It may be a 200 with an auto-submit form, or a 302 redirect
        if r2.status_code == 302:
            # Follow redirect
            r2 = self.session.get(
                r2.headers["Location"], timeout=30, allow_redirects=True,
            )

        # Check for ADFS error (login failure returns the same form again)
        if "Sign in" in r2.text and "errorText" in r2.text:
            error_match = re.search(
                r'id="errorText"[^>]*>([^<]+)', r2.text
            )
            error_msg = error_match.group(1).strip() if error_match else "Invalid credentials"
            raise ConnectionError(f"ADFS authentication failed: {error_msg}")

        # Parse the SAML token response form
        token_action, token_fields = self._parse_form(r2.text)

        if token_action and token_fields:
            # Step 5: POST the SAML token back to CRM
            if not token_action.startswith("http"):
                token_action = f"{self.crm_url}{token_action}"

            r3 = self.session.post(
                token_action, data=token_fields, timeout=30, allow_redirects=True,
            )

            # After this, the session should have CRM auth cookies
            if r3.status_code == 200:
                # Verify we can hit the API
                r_test = self.session.get(
                    self.api_base,
                    headers={"Accept": "application/json"},
                    timeout=30,
                )
                ct = r_test.headers.get("Content-Type", "")
                if "json" in ct or "odata" in ct.lower():
                    print("Successfully authenticated with Dynamics 365 via ADFS.")
                    return True
                else:
                    raise ConnectionError(
                        "ADFS auth completed but CRM API is not returning JSON. "
                        f"Content-Type: {ct}"
                    )
            else:
                raise ConnectionError(
                    f"Failed to submit SAML token to CRM: HTTP {r3.status_code}"
                )
        else:
            # Maybe the redirect chain already completed authentication
            r_test = self.session.get(
                self.api_base,
                headers={"Accept": "application/json"},
                timeout=30,
            )
            ct = r_test.headers.get("Content-Type", "")
            if "json" in ct or "odata" in ct.lower():
                print("Successfully authenticated with Dynamics 365 via ADFS.")
                return True
            else:
                raise ConnectionError(
                    "ADFS authentication flow completed but could not access the CRM API."
                )

    def _odata_headers(self, method="GET"):
        """Return OData headers appropriate for the request method."""
        headers = {
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Prefer": "odata.include-annotations=*",
        }
        if method in ("POST", "PATCH", "PUT"):
            headers["Content-Type"] = "application/json"
        return headers

    def _request(self, method, endpoint, data=None, params=None):
        """Make an authenticated request to the CRM API."""
        if not self.session:
            self.authenticate()
        url = f"{self.api_base}/{endpoint}"
        headers = self._odata_headers(method)
        response = self.session.request(
            method, url, headers=headers, json=data, params=params, timeout=30,
        )

        if response.status_code == 401:
            # Re-authenticate and retry
            self.authenticate()
            response = self.session.request(
                method, url, headers=headers, json=data, params=params, timeout=30,
            )

        if response.status_code >= 400:
            raise requests.HTTPError(
                f"CRM API error {response.status_code}: {response.text}", response=response
            )

        return response

    # ─── Lookup Maps ────────────────────────────────────────────────────

    SUBJECT_MAP = {
        "appointment": 100000000,
        "dayclose issue": 100000001,
        "drs access issue": 100000002,
        "hardware issue": 100000003,
        "internal request": 100000004,
        "internet/network issue": 100000005,
        "inventory issue": 100000006,
        "question": 100000007,
        "quote": 100000008,
        "reports issue": 100000009,
        "software issue": 100000010,
        "user error": 100000011,
        "locked buy": 100000012,
        "printer": 100000013,
        "splunk - update fixit": 100000014,
        "splunk - drsftp": 100000015,
        "splunk - server issue": 100000016,
        "splunk - pos issue": 100000017,
        "checks": 100000018,
        "winmark connect": 100000019,
    }

    CASE_TYPE_MAP = {
        "new store setup": 1,
        "reimage": 2,
        "pos": 3,
        "internet/firewall/cde": 100000000,
        "pole display": 100000001,
        "server": 100000002,
        "software/drs update": 100000003,
        "other": 100000004,
        "7 day error": 100000005,
        "dayclose failure": 100000006,
        "file in-use error": 100000007,
        "slow/freezing computer": 100000008,
        "unable to open drs": 100000009,
        "backup": 100000010,
        "battery backup": 100000011,
        "cash drawer": 100000012,
        "kvm/mouse/keyboard": 100000013,
        "printers": 100000014,
        "scanner": 100000015,
        "touch screen": 100000016,
        "brand standard": 100000017,
        "get data": 100000018,
        "cct/cde": 100000019,
        "dvr": 100000020,
        "firewall": 100000021,
        "internet issue": 100000022,
        "datascan": 100000023,
        "rgis": 100000024,
        "inventory": 100000025,
        "operational": 100000026,
        "report": 100000027,
        "technical": 100000028,
        "new store": 100000029,
        "peripheral": 100000030,
        "status update": 100000031,
        "buy reports": 100000032,
        "inventory reports": 100000033,
        "reg/day/month/year": 100000034,
        "buy system issue": 100000035,
        "general drs issue": 100000036,
        "locked buy": 100000037,
        "software update": 100000038,
        "third party": 100000039,
        "virus": 100000040,
        "windows issue": 100000041,
        "wrong amount": 100000042,
        "unsupported": 100000043,
        "winmark remote": 100000044,
        "quoted": 100000045,
        "closed": 100000046,
        "topay tender": 100000047,
        "topay tender items": 100000048,
        "toinv": 100000049,
        "topay": 100000050,
        "active": 100000051,
        "ingenico": 100000052,
        "label": 100000053,
        "receipt": 100000054,
        "report/check": 100000055,
        "preinventory": 100000056,
        "hardware": 100000057,
        "ftp loop": 100000058,
        "sacheck": 100000059,
        "non-start point": 100000060,
        "hdd space": 100000061,
        "backup failure": 100000062,
        "low ip address": 100000063,
        "cf late": 100000064,
        "questions": 100000065,
        "issues": 100000066,
        "password reset": 100000067,
        "drs messaging service": 100000068,
        "tango": 100000069,
    }

    @classmethod
    def resolve_subject(cls, value):
        """Resolve a subject name or code to its integer code."""
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return int(value)
        lookup = value.strip().lower()
        if lookup in cls.SUBJECT_MAP:
            return cls.SUBJECT_MAP[lookup]
        raise ValueError(
            f"Unknown subject '{value}'. Valid subjects: {', '.join(cls.SUBJECT_MAP.keys())}"
        )

    @classmethod
    def resolve_case_type(cls, value):
        """Resolve a case type name or code to its integer code. Returns None if unknown."""
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return int(value)
        lookup = value.strip().lower()
        # Exact match first
        if lookup in cls.CASE_TYPE_MAP:
            return cls.CASE_TYPE_MAP[lookup]
        # Match on first word (e.g. "POS Install" → "pos")
        first_word = lookup.split()[0] if lookup.split() else ""
        if first_word in cls.CASE_TYPE_MAP:
            return cls.CASE_TYPE_MAP[first_word]
        print(f"Warning: Unknown case type '{value}', skipping. "
              f"Valid types: {', '.join(cls.CASE_TYPE_MAP.keys())}")
        return None

    @staticmethod
    def parse_received_on(value):
        """Parse a received-on datetime string to ISO 8601 UTC format."""
        formats = [
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        raise ValueError(
            f"Could not parse date '{value}'. Use format: MM/DD/YYYY HH:MM AM/PM"
        )

    # ─── Case Management ────────────────────────────────────────────────

    def lookup_account_by_store(self, store_number):
        """Look up an account by its store number (win_storenumber)."""
        params = {
            "$top": 1,
            "$filter": f"accountnumber eq '{store_number}'",
            "$select": "accountid,name,accountnumber",
        }
        response = self._request("GET", "accounts", params=params)
        accounts = response.json().get("value", [])
        if not accounts:
            raise ValueError(f"No account found for store number '{store_number}'.")
        return accounts[0]

    def create_case(self, description, account_id=None, store_number=None,
                    priority=None, contact=None, contact_phone=None,
                    subject=None, case_type=None, received_on=None,
                    origin=None, **extra_fields):
        """
        Create a new case (incident) in Dynamics 365.

        Args:
            description: Case description
            account_id: GUID of the customer account (required if no store_number)
            store_number: Store number to look up the account (alternative to account_id)
            priority: Priority code (1=High, 2=Normal, 3=Low)
            contact: Contact name (win_contact)
            subject: Subject name or code (win_subject)
            case_type: Case type name or code (casetypecode)
            received_on: Received datetime string (MM/DD/YYYY HH:MM AM/PM)
            origin: Case origin code (caseorigincode)
            **extra_fields: Any additional fields to set on the case

        Returns:
            dict with the created case ID and details
        """
        # Look up account by store number if needed
        if store_number and not account_id:
            account = self.lookup_account_by_store(store_number)
            account_id = account["accountid"]
            print(f"Found account: {account.get('name', '')} (store {store_number})")

        if not account_id:
            raise ValueError("Either account_id or store_number is required to create a case.")

        case_data = {
            "description": description,
            "customerid_account@odata.bind": f"/accounts({account_id})",
        }

        if store_number:
            case_data["win_storenumber"] = store_number

        if priority is not None:
            case_data["prioritycode"] = priority
        if contact:
            case_data["win_contact"] = contact
        if contact_phone:
            case_data["win_contactphone"] = contact_phone
        if subject is not None:
            case_data["win_subject"] = self.resolve_subject(subject)
        if case_type is not None:
            resolved_type = self.resolve_case_type(case_type)
            if resolved_type is not None:
                case_data["casetypecode"] = resolved_type
        if received_on is not None:
            case_data["win_receivedon"] = self.parse_received_on(received_on)
        if origin is not None:
            case_data["caseorigincode"] = origin

        case_data.update(extra_fields)

        response = self._request("POST", "incidents", data=case_data)

        if response.status_code in (201, 204):
            case_id = response.headers.get("OData-EntityId", "")
            # Extract GUID from the entity URL
            if "(" in case_id:
                case_id = case_id.split("(")[-1].rstrip(")")
            print(f"Case created successfully. ID: {case_id}")
            return {"case_id": case_id, "description": description, "status": "created"}
        else:
            raise Exception(f"Failed to create case: {response.text}")

    def get_case(self, case_id):
        """Retrieve a single case by its GUID."""
        response = self._request("GET", f"incidents({case_id})")
        return response.json()

    def list_cases(self, top=50, filters=None, select=None):
        """
        List cases with optional OData filtering.

        Args:
            top: Max number of results (default 50)
            filters: OData $filter string (e.g. "statecode eq 0")
            select: Comma-separated field names to return

        Returns:
            List of case records
        """
        params = {
            "$top": top,
            "$orderby": "createdon desc",
        }
        if filters:
            params["$filter"] = filters
        if select:
            params["$select"] = select

        response = self._request("GET", "incidents", params=params)
        data = response.json()
        return data.get("value", [])

    def update_case(self, case_id, **fields):
        """Update an existing case with the provided fields."""
        response = self._request("PATCH", f"incidents({case_id})", data=fields)
        if response.status_code == 204:
            print(f"Case {case_id} updated successfully.")
            return True
        raise Exception(f"Failed to update case: {response.text}")

    # ─── Reports ────────────────────────────────────────────────────────

    def list_reports(self, top=50, name_filter=None):
        """
        List available reports in the CRM.

        Args:
            top: Max results
            name_filter: Optional partial name to search for

        Returns:
            List of report records
        """
        params = {
            "$top": top,
            "$select": "reportid,name,description,createdon,modifiedon",
        }
        if name_filter:
            params["$filter"] = f"contains(name,'{name_filter}')"

        response = self._request("GET", "reports", params=params)
        data = response.json()
        return data.get("value", [])

    def get_report(self, report_id):
        """Retrieve details of a specific report by GUID."""
        response = self._request("GET", f"reports({report_id})")
        return response.json()

    # ─── Contacts & Accounts (helpers) ──────────────────────────────────

    def search_contacts(self, search_term, top=10):
        """Search contacts by name or email."""
        params = {
            "$top": top,
            "$filter": (
                f"contains(fullname,'{search_term}') "
                f"or contains(emailaddress1,'{search_term}')"
            ),
            "$select": "contactid,fullname,emailaddress1,telephone1",
        }
        response = self._request("GET", "contacts", params=params)
        return response.json().get("value", [])

    def search_accounts(self, search_term, top=10):
        """Search accounts by name."""
        params = {
            "$top": top,
            "$filter": f"contains(name,'{search_term}')",
            "$select": "accountid,name,emailaddress1,telephone1",
        }
        response = self._request("GET", "accounts", params=params)
        return response.json().get("value", [])


# ─── Convenience CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dynamics 365 CRM CLI")
    sub = parser.add_subparsers(dest="command")

    # create-case
    cc = sub.add_parser("create-case", help="Create a new case")
    cc.add_argument("--store", required=True, help="Store number")
    cc.add_argument("--description", required=True)
    cc.add_argument("--subject", required=True, help="Subject (e.g. 'Software Issue', 'Hardware Issue')")
    cc.add_argument("--case-type", default=None, help="Case type (e.g. 'POS', 'Technical', 'Tango')")
    cc.add_argument("--received-on", default=None, help="Received on (MM/DD/YYYY HH:MM AM/PM)")
    cc.add_argument("--contact", default=None, help="Contact name")
    cc.add_argument("--priority", type=int, choices=[1, 2, 3], default=2)
    cc.add_argument("--origin", type=int, default=None, help="Origin code (1=Phone, 2=Email, 3=Web)")

    # list-cases
    lc = sub.add_parser("list-cases", help="List cases")
    lc.add_argument("--top", type=int, default=20)
    lc.add_argument("--filter", default=None)

    # list-reports
    lr = sub.add_parser("list-reports", help="List reports")
    lr.add_argument("--top", type=int, default=20)
    lr.add_argument("--name", default=None)

    # test-auth
    sub.add_parser("test-auth", help="Test CRM authentication")

    args = parser.parse_args()
    client = Dynamics365Client()

    if args.command == "test-auth":
        client.authenticate()
        print("Authentication successful!")

    elif args.command == "create-case":
        client.create_case(
            store_number=args.store,
            description=args.description,
            subject=args.subject,
            case_type=args.case_type,
            received_on=args.received_on,
            contact=args.contact,
            priority=args.priority,
            origin=args.origin,
        )

    elif args.command == "list-cases":
        cases = client.list_cases(top=args.top, filters=args.filter)
        for c in cases:
            ticket = c.get("ticketnumber", "")
            store = c.get("win_storenumber", "")
            contact = c.get("win_contact", "")
            subject = c.get("win_subject@OData.Community.Display.V1.FormattedValue", "")
            origin = c.get("caseorigincode@OData.Community.Display.V1.FormattedValue", "")
            desc = c.get("description", "") or ""
            print(f"  [{ticket}] Store: {store} | Contact: {contact} | "
                  f"Subject: {subject} | Origin: {origin}")
            if desc:
                print(f"    Description: {desc[:120]}")

    elif args.command == "list-reports":
        reports = client.list_reports(top=args.top, name_filter=args.name)
        for r in reports:
            print(f"  [{r.get('reportid', '?')}] {r.get('name', 'Unnamed')}")

    else:
        parser.print_help()
