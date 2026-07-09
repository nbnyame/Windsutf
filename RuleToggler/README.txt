========================================================================
  SUPPORT CENTER INBOX RULE TOGGLE  —  Setup Guide
  Mailbox : supportcenter@winmarkcorporation.com
  Rule    : "Automate making all Cases (Nana test rule)"
========================================================================

OVERVIEW
--------
This tool lets any user toggle the inbox rule on/off with a simple GUI.
Credentials are embedded (obfuscated) inside the compiled .exe — no one
running the tool ever sees or needs login details.

It reuses the EXISTING Azure AD app registration already configured in
Dynamics365CRM/.env (the same one used by the pollers). You do NOT need
to create a new app — you only need to add one extra permission to it.

App registration in use:
  Client ID : 0b1f70a7-4bc6-4114-9c72-bc6af340525d
  Tenant ID : 2c76733e-483c-4d32-94d1-06a7dee7bf54

------------------------------------------------------------------------
STEP 1  —  Add MailboxSettings.ReadWrite to the existing app  (one-time)
------------------------------------------------------------------------
The existing app already has Mail.Read / Mail.ReadWrite for the pollers.
Toggling inbox rules requires one additional permission.

1. Open https://portal.azure.com and sign in as a Global Admin.

2. Go to:  Azure Active Directory > App registrations
   Search for / open the app with Client ID:
   0b1f70a7-4bc6-4114-9c72-bc6af340525d

3. Go to:  API permissions > Add a permission > Microsoft Graph
           > Application permissions
   Search for and add:  MailboxSettings.ReadWrite
   Click  Grant admin consent for Winmark Corporation.
   Wait until the Status column shows a green checkmark.

That's it — no new app, no new secret needed.

------------------------------------------------------------------------
STEP 2  —  Encode credentials  (admin only, one-time)
------------------------------------------------------------------------
1. From the RuleToggler folder, run:
      python encode_creds.py
   It automatically reads AZURE_TENANT_ID / AZURE_CLIENT_ID /
   AZURE_CLIENT_SECRET from Dynamics365CRM/.env.

2. It prints three _VARIABLE = "..." lines. Copy all three.

3. Open  rule_toggle.py  and replace the three placeholder lines in the
   "ENCODED CREDENTIALS" section with what you just copied.

4. DELETE encode_creds.py — do not leave it on disk.

------------------------------------------------------------------------
STEP 3  —  Build the .exe
------------------------------------------------------------------------
1. Make sure Python is installed:  https://python.org  (add to PATH)
2. Double-click  build.bat
   It installs the required packages and compiles the exe automatically.
3. The finished exe is at:  dist\SupportCenter Rule Toggle.exe

------------------------------------------------------------------------
STEP 4  —  Deploy
------------------------------------------------------------------------
Copy   dist\SupportCenter Rule Toggle.exe
To     K:\02-SOFTWARE\Support Center Inbox\

Any user who can open that share can run the tool immediately —
no installation, no credentials, no PowerShell.

------------------------------------------------------------------------
TROUBLESHOOTING
------------------------------------------------------------------------
"Authentication failed"       Recheck TENANT_ID / CLIENT_ID / SECRET in
                              encode_creds.py and rebuild.

"Rule not found"              Verify the exact rule name in Outlook matches:
                              "Automate making all Cases (Nana test rule)"

"Forbidden (403)"             Admin consent was not granted in Step 1-5.
                              Return to Azure AD and grant consent again.

"Rule not found" after rename If the rule was renamed in Outlook, update
                              RULE_NAME in rule_toggle.py and rebuild.

Client secret expired         Create a new secret in Azure AD (Step 1-4),
                              re-run encode_creds.py, update rule_toggle.py,
                              and rebuild the .exe.
========================================================================
