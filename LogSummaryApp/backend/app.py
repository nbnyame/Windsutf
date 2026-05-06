from flask import Flask, jsonify, request
from flask_cors import CORS
import re
from datetime import datetime, date
from pathlib import Path

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent.parent.parent
POLLER_LOG = BASE_DIR / 'poller.log'
DRS_POLLER_LOG = BASE_DIR / 'drs_poller.log'

def parse_case_created(log_file, filter_date=None):
    """Parse case creation events from poller.log with account, subject, and status"""
    cases = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # Look for "Case created" line - handle both old and new formats
            # Old format: Case created for store 80999: 1f876737-5d49-f111-a60d-005056ad6d42
            # New format: Case created for store 80999: CAS-362884-V3M9W4 (ID: 1f876737-5d49-f111-a60d-005056ad6d42)
            case_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] Case created for store (\d+): (?:CAS-[A-Z0-9-]+ \(ID: )?([a-f0-9-]+)\)?', line)
            if case_match:
                timestamp_str, store_num, case_id = case_match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                # Filter by date if specified
                if filter_date:
                    if timestamp.date() != filter_date:
                        continue
                
                # Look backwards for the Params line (can be 7-10 lines before due to intermediate log messages)
                account = 'Unknown'
                subject = 'No subject'
                case_type = 'Unknown'
                status = 'Processed'
                time_difference = None
                
                for j in range(max(0, i-10), i):
                    params_match = re.search(r'Params: contact=([^,]+), phone=[^,]+, subject=([^,]+), case_type=(.+)', lines[j])
                    if params_match:
                        account = params_match.group(1)
                        subject = params_match.group(2)
                        case_type = params_match.group(3).strip()
                        break
                
                # Look for status in nearby lines
                for j in range(max(0, i-3), min(len(lines), i+2)):
                    if 'status updated to' in lines[j]:
                        status_match = re.search(r"status updated to '([^']+)'", lines[j])
                        if status_match:
                            status = status_match.group(1)
                            break
                
                # Look forward for Time Difference (in new format, it appears after Case created line)
                for j in range(i+1, min(len(lines), i+5)):
                    time_diff_match = re.search(r'Time Difference: (.+?) \(Created - Received\)', lines[j])
                    if time_diff_match:
                        time_difference = time_diff_match.group(1)
                        break
                
                cases.append({
                    'timestamp': timestamp.isoformat(),
                    'store': store_num,
                    'case_id': case_id,
                    'account': account,
                    'subject': subject,
                    'case_type': case_type,
                    'status': status,
                    'time_difference': time_difference,
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
    except FileNotFoundError:
        pass
    
    return updates

def parse_duplicates_increments(log_file, filter_date=None):
    """Parse duplicate/increment events from poller.log"""
    duplicates = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # Look for "marked as Processed" with any duplicate/increment type in parentheses
            # Use a more flexible pattern to capture nested parentheses
            increment_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\]\s+Item (\d+) marked as Processed \((.+?)\)\.', line)
            if increment_match:
                timestamp_str, item_num, status_type = increment_match.groups()
                # Only process if it's a duplicate/increment type (not other statuses)
                if status_type not in ['increment', 'same-day', 'same-subject', 'duplicate (within 5 min)']:
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
                
                # Second pass: check for Exact duplicate first (true duplicates)
                for j in range(max(0, i-15), i):
                    if 'Exact duplicate' in lines[j]:
                        is_increment = False
                        dup_match = re.search(r'Exact duplicate \((.+?)\):', lines[j])
                        if dup_match:
                            duplicate_type = dup_match.group(1)
                        break
                
                # Third pass: if not exact duplicate, look for Increment or old Duplicate format (within 5 lines)
                if is_increment:
                    for j in range(max(0, i-5), i):
                        if '  Increment' in lines[j]:
                            inc_match = re.search(r'Increment \(([^)]+)\):', lines[j])
                            if inc_match:
                                duplicate_type = inc_match.group(1)
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
                    'status': 'Increment' if is_increment else 'Duplicate',
                    'type': 'duplicate_increment'
                })
    except FileNotFoundError:
        pass
    
    return duplicates

def parse_errors(log_file, filter_date=None):
    """Parse error messages from poller.log"""
    errors = []
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[ERROR\] (.+)'
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(pattern, line)
                if match:
                    timestamp_str, error_msg = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Filter by date if specified
                    if filter_date:
                        if timestamp.date() != filter_date:
                            continue
                    
                    errors.append({
                        'timestamp': timestamp.isoformat(),
                        'message': error_msg,
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'poller_log_exists': POLLER_LOG.exists(),
        'drs_poller_log_exists': DRS_POLLER_LOG.exists()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
