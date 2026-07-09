"""
DRS Version Audit Tool
======================
Connects to Dynamics 365 CRM and finds all open stores running DRS 8.9.6 or lower.

Results are sorted by time zone in this priority order:
  1. Pacific (PT)
  2. Mountain (MT)
  3. Central (CT)
  4. Eastern (ET)
  5. Atlantic (AT)
  6. Unknown / other

Usage:
  python drs_version_audit.py                   Run audit and print results
  python drs_version_audit.py --csv             Also export results to CSV
  python drs_version_audit.py --max-version 8.9.5  Override the max DRS version threshold
  python drs_version_audit.py --discover-fields <store_number>
                                                Inspect a store's account fields (for setup)
  python drs_version_audit.py --list-drs-versions
                                                List all DRS version options in CRM
  python drs_version_audit.py --tz-field <field_name>
                                                Override the CRM timezone field name
                                                (default: auto-discover from env or common names)

Environment variables (in Dynamics365CRM/.env):
  CRM_URL, CRM_DOMAIN, CRM_USERNAME, CRM_PASSWORD  - CRM authentication
  CRM_DRS_VERSION_FIELD  - DRS version field on account (default: win_drsversion1)
  CRM_TIMEZONE_FIELD     - Timezone field on account (default: auto-detect)
"""

import os
import re
import csv
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load .env from the parent directory (Dynamics365CRM/)
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PARENT_DIR, ".env"))

# ─── Configuration ────────────────────────────────────────────────────────────

CRM_DRS_VERSION_FIELD   = os.getenv("CRM_DRS_VERSION_FIELD", "win_drsversion1")
CRM_TIMEZONE_FIELD      = os.getenv("CRM_TIMEZONE_FIELD", "")
CRM_SERVER_MODEL_FIELD  = "win_servermodel"

# Server model option codes to EXCLUDE (G10 w/vG9 and lower).
# Codes 100000000–100000009 map to: ML110 G5b/G5c/G6/G7/G8v1/G8v2/Not Supported/None/G9/G10-w/vG9
EXCLUDED_SERVER_MODEL_CODES = set(range(100000000, 100000010))

# Ordered list of timezone "buckets" — sort priority (lowest index = first)
TIMEZONE_ORDER = ["PT", "MT", "CT", "ET", "AT"]

# Keywords to classify a timezone label/value into a bucket
TIMEZONE_KEYWORDS = {
    "PT": ["pacific", "pt", "pst", "pdt"],
    "MT": ["mountain", "mt", "mst", "mdt"],
    "CT": ["central", "ct", "cst", "cdt"],
    "ET": ["eastern", "et", "est", "edt"],
    "AT": ["atlantic", "at", "ast", "adt"],
}

# Candidate field names to probe when auto-detecting the timezone field
TIMEZONE_FIELD_CANDIDATES = [
    "win_timezone",
    "win_timezone1",
    "win_storetimezone",
    "win_tz",
    "win_time_zone",
    "new_timezone",
]

# ─── Version Parsing ──────────────────────────────────────────────────────────

def _parse_version_tuple(label):
    """
    Extract a numeric version tuple from a DRS version label string.
    E.g. "8.9.7 General (322)" -> (8, 9, 7)
         "8.9.6"               -> (8, 9, 6)
    Returns None if no version number found.
    """
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', str(label))
    if match:
        return tuple(int(x) for x in match.groups())
    return None


def _is_version_at_or_below(label, max_version_str):
    """
    Return True if the DRS version label is <= the max_version string.
    E.g. label="8.9.6 General (300)", max_version_str="8.9.6" -> True
         label="8.9.7 General (322)", max_version_str="8.9.6" -> False
    """
    label_ver = _parse_version_tuple(label)
    max_ver = _parse_version_tuple(max_version_str)
    if label_ver is None or max_ver is None:
        return False
    return label_ver <= max_ver


# ─── Timezone Classification ──────────────────────────────────────────────────

def _classify_timezone(tz_value):
    """
    Map a raw timezone label/string to a timezone bucket (PT, MT, CT, ET, AT).
    Returns "Unknown" if no match.
    """
    if not tz_value:
        return "Unknown"
    lower = str(tz_value).strip().lower()
    for bucket, keywords in TIMEZONE_KEYWORDS.items():
        for kw in keywords:
            # Match as whole word or start-of-string to avoid false positives
            if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                return bucket
    return "Unknown"


def _timezone_sort_key(bucket):
    """Return the sort index for a timezone bucket (lower = first)."""
    try:
        return TIMEZONE_ORDER.index(bucket)
    except ValueError:
        return len(TIMEZONE_ORDER)  # Unknown goes last


# ─── Field Auto-Detection ─────────────────────────────────────────────────────

def discover_timezone_field(crm_client, sample_account_id):
    """
    Try each candidate timezone field name one at a time on a sample account.
    Returns the first field name that contains a non-null, non-empty value,
    or None if none found.
    """
    print("\n[Auto-detect] Probing timezone field candidates on a sample account...")
    for field in TIMEZONE_FIELD_CANDIDATES:
        try:
            account = crm_client.get_account(
                sample_account_id,
                select=field,
            )
            val = account.get(field)
            # Also check formatted value annotation (returned automatically)
            fv_key = f"{field}@OData.Community.Display.V1.FormattedValue"
            fv_val = account.get(fv_key)
            display_val = fv_val or val
            if display_val is not None and str(display_val).strip():
                print(f"  Found timezone field: '{field}' = '{display_val}'")
                return field
        except Exception:
            pass  # Field doesn't exist on this entity — try next

    print("  No timezone field found among candidates.")
    return None


# ─── Core Audit Logic ─────────────────────────────────────────────────────────

def fetch_all_open_accounts_with_drs(crm_client, drs_field, tz_field=None):
    """
    Page through ALL active (open) accounts and return those that have a
    DRS version set. Uses $skiptoken pagination to handle large result sets.

    Returns a list of dicts with keys:
      store_number, name, account_id, drs_label, drs_code, tz_raw, tz_bucket
    """
    # Note: annotation suffixes like @OData.Community.Display.V1.FormattedValue
    # cannot be listed in $select on CRM v8.2 — they are returned automatically
    # when the Prefer: odata.include-annotations=* header is present.
    select_fields = [
        "accountid",
        "accountnumber",
        "name",
        drs_field,
        CRM_SERVER_MODEL_FIELD,
    ]
    if tz_field:
        select_fields.append(tz_field)

    params = {
        "$filter": f"statecode eq 0 and {drs_field} ne null",
        "$select": ",".join(select_fields),
        "$top": 5000,
        "$orderby": "accountnumber asc",
    }

    all_accounts = []
    endpoint = "accounts"
    page = 1

    while endpoint:
        print(f"  Fetching page {page}...", end="\r")
        response = crm_client._request("GET", endpoint, params=params if page == 1 else None)
        data = response.json()
        accounts = data.get("value", [])
        all_accounts.extend(accounts)

        # OData next-link for pagination
        next_link = data.get("@odata.nextLink")
        if next_link:
            # Strip the base URL — _request() will prepend it
            endpoint = next_link.replace(crm_client.api_base + "/", "")
            page += 1
        else:
            endpoint = None

    print(f"  Fetched {len(all_accounts)} accounts with DRS version set.          ")
    return all_accounts


def build_drs_option_map(crm_client, drs_field):
    """
    Return a dict: {option_code (int): label (str)} for the DRS version OptionSet.
    Also returns the inverse: {label (str): code (int)}.
    """
    print(f"Loading DRS version options from CRM field '{drs_field}'...")
    raw_map = crm_client.get_option_set_values("account", drs_field)
    # raw_map is {lowercase_label: code}
    label_to_code = raw_map
    code_to_label = {v: k for k, v in raw_map.items()}
    return label_to_code, code_to_label


def run_audit(crm_client, drs_field, tz_field, max_version_str, code_to_label):
    """
    Fetch all accounts, filter to those with DRS <= max_version, classify
    timezone, and return a sorted list of result dicts.
    """
    print(f"\nSearching all open stores with DRS version <= {max_version_str}...\n")

    all_accounts = fetch_all_open_accounts_with_drs(crm_client, drs_field, tz_field)

    results = []
    for acct in all_accounts:
        drs_code = acct.get(drs_field)

        # Get the human-readable DRS label
        drs_label = acct.get(
            f"{drs_field}@OData.Community.Display.V1.FormattedValue", ""
        )
        if not drs_label and drs_code is not None:
            drs_label = code_to_label.get(drs_code, str(drs_code))

        if not drs_label:
            continue

        # Filter: skip stores with old/unsupported server hardware (G10 w/vG9 or lower)
        server_code = acct.get(CRM_SERVER_MODEL_FIELD)
        if server_code is not None and int(server_code) in EXCLUDED_SERVER_MODEL_CODES:
            continue

        # Filter: only include versions at or below the threshold
        if not _is_version_at_or_below(drs_label, max_version_str):
            continue

        # Get timezone
        tz_raw = ""
        if tz_field:
            tz_raw = acct.get(
                f"{tz_field}@OData.Community.Display.V1.FormattedValue", ""
            ) or str(acct.get(tz_field, "") or "")

        tz_bucket = _classify_timezone(tz_raw)

        server_label = acct.get(
            f"{CRM_SERVER_MODEL_FIELD}@OData.Community.Display.V1.FormattedValue", ""
        ) or str(acct.get(CRM_SERVER_MODEL_FIELD, "") or "")

        results.append({
            "store_number":  acct.get("accountnumber", ""),
            "name":          acct.get("name", ""),
            "account_id":    acct.get("accountid", ""),
            "drs_label":     drs_label,
            "drs_version":   _parse_version_tuple(drs_label),
            "tz_raw":        tz_raw,
            "tz_bucket":     tz_bucket,
            "server_model":  server_label,
        })

    # Sort: primary = timezone order (PT first), secondary = version descending (newest first), tertiary = store number
    results.sort(key=lambda r: (
        _timezone_sort_key(r["tz_bucket"]),
        tuple(-x for x in r["drs_version"]) if r["drs_version"] else (0,),
        r["store_number"],
    ))

    return results


# ─── Output Formatting ────────────────────────────────────────────────────────

def print_results(results, max_version_str):
    """Print a formatted table of results to stdout."""
    if not results:
        print(f"\nNo open stores found running DRS {max_version_str} or lower.")
        return

    print(f"\n{'='*78}")
    print(f"  STORES ON DRS {max_version_str} OR LOWER  ({len(results)} found)")
    print(f"{'='*78}")
    print(f"  {'TZ':<5}  {'Store':<8}  {'DRS Version':<35}  Store Name")
    print(f"  {'-'*5}  {'-'*8}  {'-'*35}  {'-'*30}")

    current_tz = None
    for r in results:
        if r["tz_bucket"] != current_tz:
            current_tz = r["tz_bucket"]
            bucket_label = current_tz if current_tz != "Unknown" else "Unknown / Other"
            print(f"\n  -- {bucket_label} --")

        print(
            f"  {r['tz_bucket']:<5}  "
            f"{r['store_number']:<8}  "
            f"{r['drs_label']:<35}  "
            f"{r['name']}"
        )

    print(f"\n{'='*78}")
    print(f"  Total: {len(results)} store(s)\n")


def export_csv(results, max_version_str):
    """Write results to a timestamped CSV file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(
        os.path.dirname(__file__),
        f"drs_audit_{max_version_str.replace('.', '_')}_{ts}.csv",
    )
    fieldnames = ["timezone", "store_number", "store_name", "drs_version", "account_id"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "timezone":     r["tz_bucket"],
                "store_number": r["store_number"],
                "store_name":   r["name"],
                "drs_version":  r["drs_label"],
                "account_id":   r["account_id"],
            })
    print(f"CSV exported: {filename}")
    return filename


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find open stores running DRS 8.9.6 or lower, sorted by time zone.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python drs_version_audit.py
  python drs_version_audit.py --csv
  python drs_version_audit.py --max-version 8.9.5
  python drs_version_audit.py --tz-field win_timezone
  python drs_version_audit.py --discover-fields 12345
  python drs_version_audit.py --list-drs-versions
        """,
    )
    parser.add_argument(
        "--max-version", default="8.9.6",
        help="Maximum DRS version to include (default: 8.9.6)",
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="Export results to a CSV file",
    )
    parser.add_argument(
        "--tz-field", default=None,
        help="CRM account field name for timezone (overrides auto-detect)",
    )
    parser.add_argument(
        "--drs-field", default=None,
        help=f"CRM account field name for DRS version (default: {CRM_DRS_VERSION_FIELD})",
    )
    parser.add_argument(
        "--discover-fields", metavar="STORE_NUMBER",
        help="Print all fields for a given store's account record, then exit",
    )
    parser.add_argument(
        "--list-drs-versions", action="store_true",
        help="List all DRS version option values from CRM, then exit",
    )
    args = parser.parse_args()

    drs_field = args.drs_field or CRM_DRS_VERSION_FIELD

    # ── Import CRM client from parent directory ──
    sys.path.insert(0, _PARENT_DIR)
    from crm_client import Dynamics365Client

    crm = Dynamics365Client()
    print("Authenticating with Dynamics 365 CRM...")
    crm.authenticate()
    print("Authentication successful.\n")

    # ── --list-drs-versions ──
    if args.list_drs_versions:
        try:
            options = crm.get_option_set_values("account", drs_field)
            print(f"\nAvailable DRS Version options for field '{drs_field}' ({len(options)}):\n")
            for label, code in sorted(options.items(), key=lambda x: x[1]):
                ver = _parse_version_tuple(label)
                flag = " <-- BELOW THRESHOLD" if ver and _is_version_at_or_below(label, args.max_version) else ""
                print(f"  [{code:>6}]  {label}{flag}")
        except Exception as e:
            print(f"Error fetching DRS version options: {e}")
        return

    # ── --discover-fields ──
    if args.discover_fields:
        store_number = args.discover_fields.strip()
        print(f"Looking up account for store {store_number}...")
        try:
            account = crm.lookup_account_by_store(store_number)
            account_id = account["accountid"]
            print(f"Account found: {account.get('name')} (ID: {account_id})\n")
            print("All fields on this account record:\n")
            full = crm.list_account_fields(account_id)
            # Print non-null fields sorted alphabetically
            for key in sorted(full.keys()):
                val = full[key]
                if val is not None and str(val).strip():
                    print(f"  {key:<55}  =  {val}")
        except Exception as e:
            print(f"Error: {e}")
        return

    # ── Main audit ──
    # 1. Load DRS version option map
    try:
        label_to_code, code_to_label = build_drs_option_map(crm, drs_field)
    except Exception as e:
        print(f"Error loading DRS version options: {e}")
        sys.exit(1)

    # 2. Determine timezone field
    tz_field = args.tz_field or CRM_TIMEZONE_FIELD or None
    if not tz_field:
        # Auto-detect: grab a sample account to probe
        print("Timezone field not configured — attempting auto-detection...")
        sample_params = {
            "$filter": "statecode eq 0",
            "$select": "accountid",
            "$top": 1,
        }
        try:
            sample_resp = crm._request("GET", "accounts", params=sample_params)
            sample_accounts = sample_resp.json().get("value", [])
            if sample_accounts:
                sample_id = sample_accounts[0]["accountid"]
                tz_field = discover_timezone_field(crm, sample_id)
                if tz_field:
                    print(f"  Using timezone field: '{tz_field}'")
                    print(f"  Tip: Set CRM_TIMEZONE_FIELD={tz_field} in your .env to skip auto-detect.\n")
                else:
                    print("  WARNING: Could not auto-detect timezone field.")
                    print("  Stores will be grouped under 'Unknown' timezone.")
                    print("  Use --discover-fields <store> to find the correct field name,")
                    print("  then re-run with --tz-field <field_name> or set CRM_TIMEZONE_FIELD in .env.\n")
        except Exception as e:
            print(f"  Warning: Auto-detect failed: {e}")

    # 3. Run the audit
    try:
        results = run_audit(crm, drs_field, tz_field, args.max_version, code_to_label)
    except Exception as e:
        print(f"Error during audit: {e}")
        sys.exit(1)

    # 4. Print results
    print_results(results, args.max_version)

    # 5. Export CSV if requested
    if args.csv and results:
        export_csv(results, args.max_version)


if __name__ == "__main__":
    main()
