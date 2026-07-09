from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import re
from datetime import datetime, date
from pathlib import Path

BUILD_DIR = Path(__file__).parent.parent / 'frontend' / 'build'

app = Flask(__name__, static_folder=str(BUILD_DIR), static_url_path='')
CORS(app)

BASE_DIR = Path(__file__).parent.parent.parent
POLLER_LOG = BASE_DIR / 'poller.log'
DRS_POLLER_LOG = BASE_DIR / 'drs_poller.log'
FOLDER_MONITOR_LOG = BASE_DIR / 'folder_monitor.log'
SPLUNK_LOG = BASE_DIR / 'splunk_alert_poller.log'

def parse_folder_monitor(log_file, filter_date=None):
    """Parse folder monitor events from folder_monitor.log"""
    events = []
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in lines:
            # Stage 1 (new format): Moving to 'Create CRM Case/Retry'
            stage1_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Moving to 'Create CRM Case/Retry': '(.+?)' \(in folder for (.+?)\)",
                line
            )
            if stage1_match:
                timestamp_str, subject, duration = stage1_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                events.append({
                    'timestamp': timestamp.isoformat(),
                    'type': 'retry',
                    'action': 'moved_to_retry',
                    'subject': subject,
                    'duration': duration,
                })
                continue
            # Stage 1 (old format): Bouncing
            bounce_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Bouncing: '(.+?)' \(in folder for (.+?)\)",
                line
            )
            if bounce_match:
                timestamp_str, subject, duration = bounce_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                events.append({
                    'timestamp': timestamp.isoformat(),
                    'type': 'retry',
                    'action': 'moved_to_retry',
                    'subject': subject,
                    'duration': duration,
                })
                continue
            # Stage 2: Moving to 'Create CRM Case/Retry 2'
            stage2_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Moving to 'Create CRM Case/Retry 2': '(.+?)' \(in folder for (.+?)\)",
                line
            )
            if stage2_match:
                timestamp_str, subject, duration = stage2_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                events.append({
                    'timestamp': timestamp.isoformat(),
                    'type': 'retry',
                    'action': 'moved_to_retry2',
                    'subject': subject,
                    'duration': duration,
                })
                continue
            # Stage 3: Moving to Inbox (final escalation to manual handling)
            stage3_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Moving to Inbox: '(.+?)' \(in folder for (.+?)\)",
                line
            )
            if stage3_match:
                timestamp_str, subject, duration = stage3_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                events.append({
                    'timestamp': timestamp.isoformat(),
                    'type': 'retry',
                    'action': 'moved_to_inbox',
                    'subject': subject,
                    'duration': duration,
                })
                continue
            # Errors
            error_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[ERROR\] (.+)",
                line
            )
            if error_match:
                timestamp_str, message = error_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                events.append({
                    'timestamp': timestamp.isoformat(),
                    'type': 'retry',
                    'action': 'error',
                    'subject': None,
                    'duration': None,
                    'message': message.strip(),
                })
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'Error parsing folder monitor log: {e}')
    return events


def parse_case_created(log_file, filter_date=None):
    """Parse case creation events from poller.log with account, subject, and status"""
    cases = []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # Look for "Case created" line - handle both old and new formats
            # Old format: Case created for store 80999: 1f876737-5d49-f111-a60d-005056ad6d42
            # New format: Case created for store 80999: CAS-362884-V3M9W4 (ID: 1f876737-5d49-f111-a60d-005056ad6d42)
            case_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] Case created for store (\d+): (?:CAS-[A-Z0-9-]+ \(ID: )?([a-z0-9-]+)\)?', line)
            if case_match:
                timestamp_str, store_num, case_id = case_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                # Filter by date if specified
                if filter_date:
                    if timestamp.date() != filter_date:
                        continue
                
                # Look backwards for the Params line (can be 7-25 lines before due to intermediate log messages,
                # including time-correction lines that now appear before case creation)
                account = 'Unknown'
                subject = 'No subject'
                case_type = 'Unknown'
                status = 'Processed'
                time_difference = None
                has_red_flag = False
                email_verified = False
                draft_status = None
                phone_fallback = None
                email_rerouted = None
                current_store = store_num
                
                # Search backwards but stop when we find this store's "Processing store" line
                for j in range(i-1, max(0, i-25), -1):
                    # Check if this is the "Processing store" line for the current store
                    if 'Processing store' in lines[j]:
                        store_match = re.search(r'Processing store (\d+)', lines[j])
                        if store_match and store_match.group(1) == current_store:
                            # This is our store's processing block start, continue checking this line and stop after
                            params_match = re.search(r'Params: contact=([^,]+), phone=[^,]+, subject=([^,]+), case_type=(.+)', lines[j])
                            if params_match:
                                account = params_match.group(1)
                                subject = params_match.group(2)
                                case_type = params_match.group(3).strip()
                            break
                        elif store_match:
                            # Different store, stop searching
                            break
                    
                    params_match = re.search(r'Params: contact=([^,]+), phone=[^,]+, subject=([^,]+), case_type=(.+)', lines[j])
                    if params_match:
                        account = params_match.group(1)
                        subject = params_match.group(2)
                        case_type = params_match.group(3).strip()
                    
                    # Check for email verification (appears before Case created line)
                    # Require 'Found email' alongside [OK] to avoid false positives from
                    # old '[OK]\u0153\u2014 No email found...' (WARNING, NOT FOUND) lines.
                    if '[Email Verification]' in lines[j]:
                        if ('[OK]' in lines[j] and 'Found email' in lines[j]) or ('[INFO]' in lines[j] and 'Found email in' in lines[j]):
                            email_verified = True
                    
                    # Check for draft status (appears before Case created line)
                    if 'Found draft:' in lines[j] and 'moving to' in lines[j]:
                        draft_status = 'moved'
                    elif 'Draft moved successfully' in lines[j]:
                        draft_status = 'moved'
                    elif 'No draft found' in lines[j]:
                        draft_status = 'not_found'

                    # Phone fallback — store corrected via phone number lookup
                    if phone_fallback is None:
                        fb_match = re.search(
                            r"Phone fallback matched: store (\d+) \(([^)]+)\) via phone ([^.]+)\. Correcting store number from '([^']+)' to '([^']+)'\.",
                            lines[j])
                        if fb_match:
                            phone_fallback = {
                                'corrected_store': fb_match.group(1),
                                'account': fb_match.group(2),
                                'phone': fb_match.group(3).strip(),
                                'original_store': fb_match.group(4)
                            }

                    # Email rerouted from Inbox to origin folder after phone fallback
                    if email_rerouted is None:
                        reroute_match = re.search(
                            r"\[Email\] Marked as read and moved to 'Inbox / ([^']+)'\.",
                            lines[j])
                        if reroute_match:
                            email_rerouted = reroute_match.group(1)

                # Look for status in nearby lines
                for j in range(max(0, i-3), min(len(lines), i+2)):
                    if 'status updated to' in lines[j]:
                        status_match = re.search(r"status updated to '([^']+)'", lines[j])
                        if status_match:
                            status = status_match.group(1)
                            break
                
                # Look forward for Time Difference and other metadata (appears after Case created line)
                for j in range(i+1, min(len(lines), i+10)):
                    # Time Difference
                    time_diff_match = re.search(r'Time Difference: (.+?) \(Created - Received\)', lines[j])
                    if time_diff_match:
                        time_difference = time_diff_match.group(1)
                    
                    # Red Flag warnings
                    if '[RED FLAG]' in lines[j]:
                        has_red_flag = True
                    
                    # Email verification - check for success pattern
                    if '[Email Verification]' in lines[j] and 'Found email in' in lines[j]:
                        email_verified = True
                    
                    # Draft status
                    if 'Found draft:' in lines[j] and 'moving to' in lines[j]:
                        draft_status = 'moved'
                    elif 'Draft moved successfully' in lines[j]:
                        draft_status = 'moved'
                    elif 'No draft found' in lines[j]:
                        draft_status = 'not_found'
                
                cases.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store_num,
                    'case_id': case_id,
                    'account': account,
                    'subject': subject,
                    'case_type': case_type,
                    'status': status,
                    'time_difference': time_difference,
                    'has_red_flag': has_red_flag,
                    'email_verified': email_verified,
                    'draft_status': draft_status,
                    'phone_fallback': phone_fallback,
                    'email_rerouted': email_rerouted,
                    'type': 'case_created'
                })
    except FileNotFoundError:
        pass
    
    return cases

def parse_drs_updates(log_file, filter_date=None):
    """Parse DRS version updates and failures from drs_poller.log"""
    updates = []

    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            # Successful update: "Store X (Name): DRS Version updated to 'Y'."
            success_match = re.search(
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] Store (\d+) \(([^)]+)\): DRS Version updated to \'([^\']+)\'\.', line)
            if success_match:
                timestamp_str, store_num, account_name, drs_version = success_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                updates.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store_num,
                    'account': account_name,
                    'drs_version': drs_version,
                    'type': 'drs_update'
                })
                continue

            # Failed update: "[ERROR] Failed to process email for store X: {reason}"
            error_match = re.search(
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[ERROR\] Failed to process email for store (\d+): (.+)', line)
            if error_match:
                timestamp_str, store_num, error_msg = error_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                # Look backwards for "Processing: store=X, DRS version='Y'" context
                drs_version = 'Unknown'
                for j in range(max(0, i - 5), i):
                    proc_match = re.search(r"Processing: store=\d+, DRS version='([^']+)'", lines[j])
                    if proc_match:
                        drs_version = proc_match.group(1)
                        break
                updates.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store_num,
                    'account': 'Unknown',
                    'drs_version': drs_version,
                    'error': error_msg.strip(),
                    'type': 'drs_error'
                })
    except (FileNotFoundError, UnicodeDecodeError):
        pass

    return updates

def parse_duplicates_increments(log_file, filter_date=None):
    """Parse duplicate/increment events from poller.log"""
    duplicates = []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # Look for "marked as Processed" with any duplicate/increment type in parentheses
            # Use a more flexible pattern to capture nested parentheses
            increment_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Item (\d+) marked as Processed \((.+?)\)\.', line)
            if increment_match:
                timestamp_str, item_num, status_type = increment_match.groups()
                # Only process if it's a duplicate/increment type (not other statuses)
                # Include all increment/duplicate variations
                allowed_types = [
                    'increment', 'same-day', 'same-subject', 'duplicate (within 1 min)', 'duplicate (within 5 min)',
                    'resolved-same-day-subject', 'resolved-same-day', 'same-day-subject',
                    'linked-subject', 'resolved-linked-subject'
                ]
                if status_type not in allowed_types:
                    continue
                
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                # Filter by date if specified
                if filter_date:
                    if timestamp.date() != filter_date:
                        continue
                
                # Look backwards for store, contact, subject, case_type, and duplicate info
                store = 'Unknown'
                account = 'Unknown'
                subject = 'No subject'
                case_type = 'Unknown'
                duplicate_type = 'Unknown'
                is_increment = True  # Default to increment
                email_verified = False
                phone_fallback = None
                email_rerouted = None
                
                # First pass: get store, account, subject, case_type
                for j in range(max(0, i-15), i):
                    store_match = re.search(r'Processing store (\d+)\.\.\.', lines[j])
                    if store_match:
                        store = store_match.group(1)
                    
                    params_match = re.search(r'Params: contact=([^,]+), phone=[^,]+, subject=([^,]+), case_type=(.+)', lines[j])
                    if params_match:
                        account = params_match.group(1)
                        subject = params_match.group(2)
                        case_type = params_match.group(3).strip()
                    
                    # Check for email verification - require 'Found email' alongside [OK]
                    if '[Email Verification]' in lines[j]:
                        if ('[OK]' in lines[j] and 'Found email' in lines[j]) or ('[INFO]' in lines[j] and 'Found email in' in lines[j]):
                            email_verified = True

                    # Phone fallback — store corrected via phone number lookup
                    if phone_fallback is None:
                        fb_match = re.search(
                            r"Phone fallback matched: store (\d+) \(([^)]+)\) via phone ([^.]+)\. Correcting store number from '([^']+)' to '([^']+)'\.",
                            lines[j])
                        if fb_match:
                            phone_fallback = {
                                'corrected_store': fb_match.group(1),
                                'account': fb_match.group(2),
                                'phone': fb_match.group(3).strip(),
                                'original_store': fb_match.group(4)
                            }

                    # Email rerouted from Inbox to origin folder after phone fallback
                    if email_rerouted is None:
                        reroute_match = re.search(
                            r"\[Email\] Marked as read and moved to 'Inbox / ([^']+)'\.",
                            lines[j])
                        if reroute_match:
                            email_rerouted = reroute_match.group(1)

                # If phone fallback corrected the store, use the corrected number
                if phone_fallback:
                    store = phone_fallback['corrected_store']

                # Second pass: check for Exact duplicate first (true duplicates)
                for j in range(max(0, i-15), i):
                    if 'Exact duplicate' in lines[j]:
                        is_increment = False
                        dup_match = re.search(r'Exact duplicate \((.+?)\):', lines[j])
                        if dup_match:
                            duplicate_type = dup_match.group(1)
                        break
                
                # Third pass: if not exact duplicate, look for Increment in new format: "Increment (type):"
                if is_increment:
                    for j in range(max(0, i-10), i):
                        # New format: "Increment (same-subject):" or "Increment (resolved-same-day-subject):"
                        inc_match = re.search(r'Increment \(([^)]+)\):', lines[j])
                        if inc_match:
                            duplicate_type = inc_match.group(1)
                            break
                        # Old format fallback: "  Increment" or "  Duplicate"
                        elif '  Increment' in lines[j]:
                            inc_match_old = re.search(r'Increment \(([^)]+)\):', lines[j])
                            if inc_match_old:
                                duplicate_type = inc_match_old.group(1)
                            break
                        elif '  Duplicate' in lines[j]:
                            dup_match = re.search(r'Duplicate \(([^)]+)\):', lines[j])
                            if dup_match:
                                duplicate_type = dup_match.group(1)
                            break
                
                # Forward search: email move lines appear AFTER the anchor in production logs
                if email_rerouted is None:
                    for j in range(i + 1, min(len(lines), i + 5)):
                        reroute_match = re.search(
                            r"\[Email\] Marked as read and moved to 'Inbox / ([^']+)'\.",
                            lines[j])
                        if reroute_match:
                            email_rerouted = reroute_match.group(1)
                            break
                        # Stop if we hit the next item's processing block
                        if 'status updated to' in lines[j] or 'Found 1 approved' in lines[j]:
                            break

                duplicates.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store,
                    'account': account,
                    'subject': subject,
                    'case_type': case_type,
                    'duplicate_type': duplicate_type,
                    'is_increment': is_increment,
                    'email_verified': email_verified,
                    'phone_fallback': phone_fallback,
                    'email_rerouted': email_rerouted,
                    'status': 'Increment' if is_increment else 'Duplicate',
                    'type': 'duplicate_increment'
                })
    except FileNotFoundError:
        pass
    
    return duplicates

def parse_errors(log_file, filter_date=None):
    """Parse error messages from poller.log including validation errors and failed items"""
    errors = []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            # Match ERROR lines
            error_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[ERROR\] (.+)', line)
            if error_match:
                timestamp_str, error_msg = error_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                # Filter by date if specified
                if filter_date:
                    if timestamp.date() != filter_date:
                        continue
                
                # Extract store number if present in validation errors
                store = 'Unknown'
                item_id = None
                
                # Check for validation error format: "Validation error for item X (store Y):"
                validation_match = re.search(r'Validation error for item (\d+) \(store (\d+)\):', error_msg)
                if validation_match:
                    item_id = validation_match.group(1)
                    store = validation_match.group(2)
                
                # Check for invalid store number format: "Invalid store number for item X (store Y):"
                invalid_store_match = re.search(r'Invalid store number for item (\d+) \(store (\d+)\):', error_msg)
                if invalid_store_match:
                    item_id = invalid_store_match.group(1)
                    store = invalid_store_match.group(2)

                # Check for CRM connectivity failure: "Failed to process item X (store Y): {error}"
                crm_fail_match = re.search(r'Failed to process item (\d+) \(store (\d+)\):', error_msg)
                if crm_fail_match:
                    item_id = crm_fail_match.group(1)
                    store = crm_fail_match.group(2)

                # Check for RED FLAG errors (time difference issues)
                is_red_flag = '[RED FLAG]' in error_msg
                
                errors.append({
                    'timestamp': timestamp.isoformat(),
                    'message': error_msg,
                    'store': store,
                    'item_id': item_id,
                    'is_red_flag': is_red_flag,
                    'type': 'error'
                })
            
            # Also look for INFO lines about invalid store number items
            invalid_store_info_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Item (\d+) marked as Invalid Store Number: (.+)', line)
            if invalid_store_info_match:
                timestamp_str, item_id, reason = invalid_store_info_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                store = 'Unknown'
                for j in range(max(0, i-8), i):
                    store_match = re.search(r'Processing store (\d+)\.\.\.', lines[j])
                    if store_match:
                        store = store_match.group(1)
                        break
                errors.append({
                    'timestamp': timestamp.isoformat(),
                    'message': f'Item {item_id} marked as Invalid Store Number: {reason}',
                    'store': store,
                    'item_id': item_id,
                    'is_red_flag': False,
                    'type': 'error'
                })
            
            # Also look for test/placeholder store format: "Item X marked as Invalid Store Number (store 89999)."
            invalid_store_placeholder_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Item (\d+) marked as Invalid Store Number \(store (\d+)\)\.', line)
            if invalid_store_placeholder_match:
                timestamp_str, item_id, store = invalid_store_placeholder_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                errors.append({
                    'timestamp': timestamp.isoformat(),
                    'message': f'Item {item_id} marked as Invalid Store Number (store {store}) — test/placeholder store, skipped',
                    'store': store,
                    'item_id': item_id,
                    'is_red_flag': False,
                    'type': 'error'
                })

            # Also look for INFO lines about failed items
            failed_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Item (\d+) marked as Failed: (.+)', line)
            if failed_match:
                timestamp_str, item_id, reason = failed_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                # Filter by date if specified
                if filter_date:
                    if timestamp.date() != filter_date:
                        continue
                
                # Try to find store number in nearby lines
                store = 'Unknown'
                for j in range(max(0, i-5), i):
                    store_match = re.search(r'Processing store (\d+)\.\.\.', lines[j])
                    if store_match:
                        store = store_match.group(1)
                        break
                
                errors.append({
                    'timestamp': timestamp.isoformat(),
                    'message': f'Item {item_id} marked as Failed: {reason}',
                    'store': store,
                    'item_id': item_id,
                    'is_red_flag': False,
                    'type': 'error'
                })
    except FileNotFoundError:
        pass
    
    return errors

@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get summary of all log events - defaults to today's data"""
    # Get today's date by default
    today = date.today()
    
    cases = parse_case_created(POLLER_LOG, filter_date=today)
    drs_updates = parse_drs_updates(DRS_POLLER_LOG, filter_date=today)
    duplicates = parse_duplicates_increments(POLLER_LOG, filter_date=today)
    errors = parse_errors(POLLER_LOG, filter_date=today)
    
    # Combine and sort by timestamp (newest first)
    all_events = cases + drs_updates + duplicates + errors
    all_events.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Get recent events (last 100)
    recent_events = all_events[:100]
    
    # Separate duplicates and increments
    total_duplicates = sum(1 for d in duplicates if not d.get('is_increment', True))
    total_increments = sum(1 for d in duplicates if d.get('is_increment', True))
    
    return jsonify({
        'total_cases': len(cases),
        'total_drs_updates': len(drs_updates),
        'total_duplicates': total_duplicates,
        'total_increments': total_increments,
        'total_errors': len(errors),
        'recent_events': recent_events,
        'last_updated': datetime.now().isoformat()
    })

@app.route('/api/cases', methods=['GET'])
def get_cases():
    """Get case creation events - defaults to today, supports date parameter"""
    # Get date parameter or default to today
    date_param = request.args.get('date')
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    cases = parse_case_created(POLLER_LOG, filter_date=filter_date)
    cases.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(cases)

@app.route('/api/drs-updates', methods=['GET'])
def get_drs_updates():
    """Get DRS update events - defaults to today, supports date parameter"""
    # Get date parameter or default to today
    date_param = request.args.get('date')
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    updates = parse_drs_updates(DRS_POLLER_LOG, filter_date=filter_date)
    updates.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(updates)

@app.route('/api/duplicates', methods=['GET'])
def get_duplicates():
    """Get duplicate/increment events - defaults to today, supports date parameter"""
    # Get date parameter or default to today
    date_param = request.args.get('date')
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    duplicates = parse_duplicates_increments(POLLER_LOG, filter_date=filter_date)
    duplicates.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(duplicates)

@app.route('/api/errors', methods=['GET'])
def get_errors():
    """Get error events - defaults to today, supports date parameter"""
    # Get date parameter or default to today
    date_param = request.args.get('date')
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    errors = parse_errors(POLLER_LOG, filter_date=filter_date)
    errors.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(errors)

@app.route('/api/retries', methods=['GET'])
def get_retries():
    """Get folder monitor retry/move events"""
    date_param = request.args.get('date')
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    events = parse_folder_monitor(FOLDER_MONITOR_LOG, filter_date=filter_date)
    events.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(events)

def parse_splunk_alerts(log_file, filter_date=None):
    """Parse events from splunk_alert_poller.log"""
    events = []
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        current_cycle = None

        def finalize():
            nonlocal current_cycle
            if current_cycle:
                events.append(current_cycle)
                current_cycle = None

        for line in lines:
            # New processing cycle
            proc_match = re.search(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] Processing '(.+?)' \(type=(cf_late|non_start_point)\)",
                line
            )
            if proc_match:
                finalize()
                timestamp_str, subject, email_type = proc_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if filter_date and timestamp.date() != filter_date:
                    continue
                current_cycle = {
                    'timestamp': timestamp.isoformat(),
                    'type': 'splunk',
                    'email_type': email_type,
                    'subject': subject,
                    'cases_created': [],
                    'cases_failed': [],
                    'cases_skipped': [],
                    'stores_below_threshold': [],
                    'total_stores': 0,
                    'total_created': 0,
                    'destination': None,
                    'test_mode': False,
                }
                continue

            # Already processed — ends current cycle
            if re.search(r'\[INFO\]\s+Already processed:', line):
                finalize()
                continue

            if current_cycle is None:
                # Standalone errors outside a cycle
                err_match = re.search(
                    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[ERROR\] (.+)", line
                )
                if err_match:
                    timestamp_str, message = err_match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    if filter_date and timestamp.date() != filter_date:
                        continue
                    events.append({
                        'timestamp': timestamp.isoformat(),
                        'type': 'splunk',
                        'email_type': 'error',
                        'subject': None,
                        'message': message.strip(),
                        'cases_created': [],
                        'cases_failed': [],
                        'cases_skipped': [],
                        'stores_below_threshold': [],
                        'total_stores': 0,
                        'total_created': 0,
                        'destination': None,
                        'test_mode': False,
                    })
                continue

            # Found N stores
            found_match = re.search(r'\[INFO\]\s+Found (\d+) store\(s\)', line)
            if found_match:
                current_cycle['total_stores'] = int(found_match.group(1))
                continue

            # Store created
            created_match = re.search(r'\[INFO\]\s+Store (\d+): created (CAS-\S+)', line)
            if created_match:
                store, ticket = created_match.groups()
                current_cycle['cases_created'].append({'store': store, 'ticket': ticket})
                continue

            # Store account error
            acct_match = re.search(r'\[ERROR\]\s+Store (\d+): account error — (.+)', line)
            if acct_match:
                store, error = acct_match.groups()
                current_cycle['cases_failed'].append({'store': store, 'error': error.strip()})
                continue

            # Store failed to create case
            fail_match = re.search(r'\[ERROR\]\s+Store (\d+): failed to create case — (.+)', line)
            if fail_match:
                store, error = fail_match.groups()
                current_cycle['cases_failed'].append({'store': store, 'error': error.strip()})
                continue

            # Store below threshold
            thresh_match = re.search(r'\[INFO\]\s+Store (\d+): (\d+) day\(s\) late — below threshold, skipping\.', line)
            if thresh_match:
                store, days = thresh_match.groups()
                current_cycle['stores_below_threshold'].append({'store': store, 'days_late': int(days)})
                continue

            # Store duplicate skipped
            dup_match = re.search(r'\[INFO\]\s+Store (\d+): duplicate (CAS-\S+) — skipping\.', line)
            if dup_match:
                store, ticket = dup_match.groups()
                current_cycle['cases_skipped'].append({'store': store, 'ticket': ticket})
                continue

            # TEST_MODE cancel
            if re.search(r'\[INFO\]\s+TEST_MODE:', line):
                current_cycle['test_mode'] = True
                continue

            # Email destination
            moved_match = re.search(r'\[INFO\]\s+Email moved to (.+)\.', line)
            if moved_match:
                current_cycle['destination'] = moved_match.group(1).strip()
                continue

            # Total cases created this cycle
            total_match = re.search(r'\[INFO\] Total cases created this cycle: (\d+)', line)
            if total_match:
                current_cycle['total_created'] = int(total_match.group(1))
                continue

            # Inline errors within a cycle
            inline_err = re.search(r'\[ERROR\]\s+(.+)', line)
            if inline_err:
                current_cycle['cases_failed'].append({'store': None, 'error': inline_err.group(1).strip()})
                continue

        finalize()

    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'Error parsing splunk alert log: {e}')
    return events


@app.route('/api/splunk-alerts', methods=['GET'])
def get_splunk_alerts():
    """Return parsed Splunk alert poller events for a given date"""
    date_param = request.args.get('date')
    filter_date = None
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    events = parse_splunk_alerts(SPLUNK_LOG, filter_date=filter_date)
    events.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(events)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'poller_log_exists': POLLER_LOG.exists(),
        'drs_poller_log_exists': DRS_POLLER_LOG.exists(),
        'folder_monitor_log_exists': FOLDER_MONITOR_LOG.exists(),
        'splunk_log_exists': SPLUNK_LOG.exists()
    })

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """Serve the React frontend build"""
    target = BUILD_DIR / path
    if path and target.is_file():
        return send_from_directory(str(BUILD_DIR), path)
    return send_from_directory(str(BUILD_DIR), 'index.html')

if __name__ == '__main__':
    app.run(debug=False, port=5000)
