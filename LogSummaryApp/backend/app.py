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
                    # Match both old format (✓ Found email) and new format ([OK] Found email)
                    if '[Email Verification]' in lines[j]:
                        if '[OK]' in lines[j] or ('[INFO]' in lines[j] and 'Found email in' in lines[j]):
                            email_verified = True
                    
                    # Check for draft status (appears before Case created line)
                    if 'Found draft:' in lines[j] and 'moving to' in lines[j]:
                        draft_status = 'moved'
                    elif 'Draft moved successfully' in lines[j]:
                        draft_status = 'moved'
                    elif 'No draft found' in lines[j] and 'after retry' in lines[j]:
                        draft_status = 'not_found'
                
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
                    elif 'No draft found' in lines[j] and 'after retry' in lines[j]:
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
                    'type': 'case_created'
                })
    except FileNotFoundError:
        pass
    
    return cases

def parse_drs_updates(log_file, filter_date=None):
    """Parse DRS version updates from drs_poller.log"""
    updates = []
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] Store (\d+) \(([^)]+)\): DRS Version updated to \'([^\']+)\'\.'
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(pattern, line)
                if match:
                    timestamp_str, store_num, account_name, drs_version = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Filter by date if specified
                    if filter_date:
                        if timestamp.date() != filter_date:
                            continue
                    
                    updates.append({
                        'timestamp': timestamp.isoformat(),
                        'store': store_num,
                        'account': account_name,
                        'drs_version': drs_version,
                        'type': 'drs_update'
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
                    'increment', 'same-day', 'same-subject', 'duplicate (within 5 min)',
                    'resolved-same-day-subject', 'resolved-same-day', 'same-day-subject'
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
                    
                    # Check for email verification - match both old and new formats
                    if '[Email Verification]' in lines[j]:
                        if '[OK]' in lines[j] or ('[INFO]' in lines[j] and 'Found email in' in lines[j]):
                            email_verified = True
                
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
                
                duplicates.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store,
                    'account': account,
                    'subject': subject,
                    'case_type': case_type,
                    'duplicate_type': duplicate_type,
                    'is_increment': is_increment,
                    'email_verified': email_verified,
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'poller_log_exists': POLLER_LOG.exists(),
        'drs_poller_log_exists': DRS_POLLER_LOG.exists(),
        'folder_monitor_log_exists': FOLDER_MONITOR_LOG.exists()
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
