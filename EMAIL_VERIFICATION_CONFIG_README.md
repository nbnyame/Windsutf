# Email Verification Configuration

## Overview
The SharePoint poller verifies that emails exist in the correct mailbox folders based on the case origin. This configuration file (`email_verification_config.json`) allows you to update folder names and locations **without editing code**.

## Configuration File Location
```
Dynamics365CRM/email_verification_config.json
```

## How It Works

When a case is created, the poller:
1. Reads the **Origin** field from SharePoint (e.g., "Voice to Text", "Email", "Splunk")
2. Looks up the corresponding configuration in `email_verification_config.json`
3. Searches for the email in the specified folder(s)
4. Optionally verifies the sender email address matches

## Configuration Structure

Each origin type has the following properties:

```json
{
  "origin_name": {
    "folders": ["Folder Name 1", "Folder Name 2"],
    "parent_folder": "Parent Folder Name or null",
    "parent_location": "Grandparent Folder Name (optional)",
    "check_sender": true/false,
    "description": "Human-readable description"
  }
}
```

### Properties Explained

| Property | Description | Example |
|----------|-------------|---------|
| `folders` | List of folder names to search | `["Emails From Franchisees", "Emails From FOMs"]` |
| `parent_folder` | Direct parent folder containing the target folder | `"Inbox"` |
| `parent_location` | Grandparent folder (for nested folders) | `"Inbox"` (when target is 2 levels deep) |
| `check_sender` | Whether to verify sender email address | `true` for Email/Internal, `false` for Voice to Text |
| `description` | Notes about this configuration | `"Email origin - searches by time AND sender"` |

### Folder Location Examples

**1. Direct child of Inbox:**
```json
"email": {
  "folders": ["Emails From Franchisees"],
  "parent_folder": "Inbox",
  "check_sender": true
}
```
This searches: `Inbox → Emails From Franchisees`

**2. Nested folder (2 levels deep):**
```json
"splunk": {
  "folders": ["Splunk Alerts"],
  "parent_folder": "INTERNAL REQUESTS",
  "parent_location": "Inbox",
  "check_sender": false
}
```
This searches: `Inbox → INTERNAL REQUESTS → Splunk Alerts`

**3. Top-level folder:**
```json
"custom": {
  "folders": ["My Custom Folder"],
  "parent_folder": null,
  "check_sender": false
}
```
This searches at the root mailbox level.

**4. Skip verification:**
```json
"web": {
  "folders": [],
  "parent_folder": null,
  "check_sender": false
}
```
Empty `folders` array means no verification is performed.

## Current Configuration

### Voice to Text / Phone
- **Folders:** `Calls Entered`
- **Location:** `Inbox → Calls Entered`
- **Sender Check:** No (time-based only)
- **Use Case:** Voicemail notifications from Zoom

### Email
- **Folders:** `Emails From Franchisees`, `Emails From FOMs`
- **Location:** `Inbox → [folder]`
- **Sender Check:** Yes (matches email address)
- **Use Case:** Direct emails from franchisees or FOMs

### Web
- **Folders:** None (skipped)
- **Sender Check:** No
- **Use Case:** Web form submissions (no email to verify)

### Internal
- **Folders:** `INTERNAL REQUESTS`
- **Location:** `Inbox → INTERNAL REQUESTS`
- **Sender Check:** Yes (matches email address)
- **Use Case:** Internal team requests

### Splunk
- **Folders:** `Splunk Alerts`
- **Location:** `Inbox → INTERNAL REQUESTS → Splunk Alerts`
- **Sender Check:** No (time-based only)
- **Use Case:** Automated Splunk alert emails

## How to Update Configuration

### Example 1: Rename a Folder

If "Calls Entered" is renamed to "Phone Calls":

```json
"voice_to_text": {
  "folders": ["Phone Calls"],  // ← Changed from "Calls Entered"
  "parent_folder": "Inbox",
  "check_sender": false
}
```

### Example 2: Move a Folder

If "INTERNAL REQUESTS" moves from Inbox to a top-level folder:

```json
"internal": {
  "folders": ["INTERNAL REQUESTS"],
  "parent_folder": null,  // ← Changed from "Inbox"
  "check_sender": true
}
```

### Example 3: Add Multiple Search Folders

If emails could be in either "Franchisee Emails" or "FOM Emails":

```json
"email": {
  "folders": ["Franchisee Emails", "FOM Emails"],  // ← Multiple folders
  "parent_folder": "Inbox",
  "check_sender": true
}
```

### Example 4: Change Nested Folder Structure

If "Splunk Alerts" moves from `Inbox → INTERNAL REQUESTS → Splunk Alerts` to `Inbox → Alerts → Splunk`:

```json
"splunk": {
  "folders": ["Splunk"],  // ← New folder name
  "parent_folder": "Alerts",  // ← New parent
  "parent_location": "Inbox",  // ← Grandparent stays the same
  "check_sender": false
}
```

## Testing Changes

After updating the configuration:

1. **Save** `email_verification_config.json`
2. **Restart** the poller (it loads the config on each case)
3. **Check logs** for email verification results:
   - `[OK] Found email in 'Folder Name'` = Success
   - `[NOT FOUND] No email found` = Failed to find
   - `Folder 'X' not found` = Configuration error

## Troubleshooting

### "Folder not found" Warning
- **Cause:** Folder name in config doesn't match exact name in mailbox
- **Solution:** Check folder name spelling and capitalization (case-sensitive!)

### "Parent folder not found" Warning
- **Cause:** `parent_folder` or `parent_location` is incorrect
- **Solution:** Verify the folder hierarchy in Outlook

### Email Not Found (But It Exists)
- **Cause:** Email might be outside the ±2 minute search window
- **Solution:** Check the `Received On` time in the case vs. actual email received time

### Config File Not Loading
- **Cause:** JSON syntax error
- **Solution:** Validate JSON at https://jsonlint.com/

## Notes

- **Case Sensitivity:** Folder names are case-sensitive. "Inbox" ≠ "inbox"
- **Pagination:** The code automatically handles mailboxes with 10+ folders
- **Non-Blocking:** If email verification fails, the case is still created (warning logged)
- **Retry Logic:** If email not found immediately, waits 30 seconds and retries once

## Support

If you need to add a new origin type or have questions, edit the config file following the examples above. The poller will automatically use the new configuration on the next run.
