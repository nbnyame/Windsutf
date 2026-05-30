"""
Folder Visibility Test
Verifies that the folder monitor can resolve and read all four folders:
  1. Create CRM Case          (Inbox child)
  2. Create CRM Case/Retry    (subfolder)
  3. Create CRM Case/Retry 2  (subfolder)
  4. Inbox                    (move destination)

Read-only — no emails are moved.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
MAILBOX       = os.getenv("DRAFT_TARGET_MAILBOX", "supportcenter@winmarkcorporation.com")
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]

# ── Folder helpers ─────────────────────────────────────────────────────────────

def list_child_folders(headers, parent_id):
    """Return {displayName: id} for all children of parent_id."""
    url = (f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{parent_id}/childFolders"
           f"?$top=50&$select=id,displayName,totalItemCount")
    result = {}
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for f in data.get("value", []):
            result[f["displayName"]] = {"id": f["id"], "count": f.get("totalItemCount", "?")}
        url = data.get("@odata.nextLink")
    return result

def get_top_level_folders(headers):
    """Return {displayName: id} for all top-level mailFolders."""
    url = (f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders"
           f"?$top=50&$select=id,displayName,totalItemCount")
    result = {}
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for f in data.get("value", []):
            result[f["displayName"]] = {"id": f["id"], "count": f.get("totalItemCount", "?")}
        url = data.get("@odata.nextLink")
    return result

def peek_messages(headers, folder_id, top=3):
    """Return up to `top` message subjects from a folder."""
    url = (f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/{folder_id}/messages"
           f"?$select=subject,receivedDateTime&$top={top}&$orderby=receivedDateTime desc")
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return [m.get("subject", "(no subject)") for m in resp.json().get("value", [])]

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\nMailbox : {MAILBOX}")
    print("=" * 60)

    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        print("ERROR: Missing .env credentials.")
        sys.exit(1)

    print("Authenticating...", end=" ", flush=True)
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("OK\n")

    results = {}

    # ── 1. Inbox ──────────────────────────────────────────────────────────────
    print("[1] Inbox")
    top_folders = get_top_level_folders(headers)
    inbox_info = top_folders.get("Inbox")
    if not inbox_info:
        # Graph may return Inbox as well-known name; try direct
        resp = requests.get(
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/Inbox?$select=id,displayName,totalItemCount",
            headers=headers, timeout=30)
        resp.raise_for_status()
        d = resp.json()
        inbox_info = {"id": d["id"], "count": d.get("totalItemCount", "?")}

    print(f"    ID    : {inbox_info['id']}")
    print(f"    Emails: {inbox_info['count']}")
    results["Inbox"] = {"ok": True, "id": inbox_info["id"]}

    # ── 2. Create CRM Case ────────────────────────────────────────────────────
    print("\n[2] Create CRM Case  (Inbox child)")
    inbox_children = list_child_folders(headers, inbox_info["id"])
    crm_info = inbox_children.get("Create CRM Case")
    if not crm_info:
        print("    ERROR: 'Create CRM Case' not found under Inbox.")
        results["Create CRM Case"] = {"ok": False}
    else:
        print(f"    ID    : {crm_info['id']}")
        print(f"    Emails: {crm_info['count']}")
        subjects = peek_messages(headers, crm_info["id"])
        for s in subjects:
            print(f"      - {s}")
        results["Create CRM Case"] = {"ok": True, "id": crm_info["id"]}

    # ── 3. Create CRM Case / Retry ────────────────────────────────────────────
    print("\n[3] Create CRM Case/Retry")
    if results.get("Create CRM Case", {}).get("ok"):
        crm_children = list_child_folders(headers, crm_info["id"])
        retry_info = crm_children.get("Retry")
        if not retry_info:
            print("    ERROR: 'Retry' subfolder not found under 'Create CRM Case'.")
            print(f"    Subfolders found: {list(crm_children.keys()) or '(none)'}")
            results["Retry"] = {"ok": False}
        else:
            print(f"    ID    : {retry_info['id']}")
            print(f"    Emails: {retry_info['count']}")
            subjects = peek_messages(headers, retry_info["id"])
            for s in subjects:
                print(f"      - {s}")
            results["Retry"] = {"ok": True, "id": retry_info["id"]}
    else:
        print("    SKIPPED (parent folder not found)")
        results["Retry"] = {"ok": False}

    # ── 4. Create CRM Case / Retry 2 ─────────────────────────────────────────
    print("\n[4] Create CRM Case/Retry 2")
    if results.get("Create CRM Case", {}).get("ok"):
        retry2_info = crm_children.get("Retry 2") if "crm_children" in dir() else None
        if retry2_info is None:
            if results.get("Create CRM Case", {}).get("ok"):
                crm_children2 = list_child_folders(headers, crm_info["id"])
                retry2_info = crm_children2.get("Retry 2")
        if not retry2_info:
            print("    ERROR: 'Retry 2' subfolder not found under 'Create CRM Case'.")
            print(f"    Subfolders found: {list(crm_children.keys()) or '(none)'}")
            results["Retry 2"] = {"ok": False}
        else:
            print(f"    ID    : {retry2_info['id']}")
            print(f"    Emails: {retry2_info['count']}")
            subjects = peek_messages(headers, retry2_info["id"])
            for s in subjects:
                print(f"      - {s}")
            results["Retry 2"] = {"ok": True, "id": retry2_info["id"]}
    else:
        print("    SKIPPED (parent folder not found)")
        results["Retry 2"] = {"ok": False}

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, info in results.items():
        status = "OK" if info["ok"] else "FAIL"
        print(f"  [{status:4s}] {name}")
        if not info["ok"]:
            all_ok = False

    print()
    if all_ok:
        print("All folders resolved successfully. Folder monitor is ready.")
    else:
        print("One or more folders could not be resolved. Check the errors above.")
    print()


if __name__ == "__main__":
    main()
