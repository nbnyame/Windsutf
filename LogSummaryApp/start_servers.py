"""
Hidden server launcher that starts Flask and React servers completely hidden
and monitors browser activity to auto-shutdown when browser closes.
"""
import subprocess
import time
import psutil
import sys
import os
from pathlib import Path
import webbrowser

# Get the app directory
APP_DIR = Path(__file__).parent
BACKEND_DIR = APP_DIR / 'backend'
FRONTEND_DIR = APP_DIR / 'frontend'

def kill_existing_servers():
    """Kill any existing Flask or Node servers"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'app.py' in cmdline or ('node' in proc.info['name'].lower() and 'react-scripts' in cmdline):
                proc.kill()
                print(f"Killed existing process: {proc.info['name']} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def start_flask_server():
    """Start Flask backend server completely hidden"""
    print("Starting Flask backend...")
    
    # Use CREATE_NO_WINDOW flag to completely hide the window
    CREATE_NO_WINDOW = 0x08000000
    
    flask_process = subprocess.Popen(
        ['python', 'app.py'],
        cwd=str(BACKEND_DIR),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print(f"Flask started (PID: {flask_process.pid})")
    return flask_process

def start_react_server():
    """Start React dev server completely hidden"""
    print("Starting React frontend...")
    
    # Use CREATE_NO_WINDOW flag to completely hide the window
    CREATE_NO_WINDOW = 0x08000000
    
    # Set environment variable to prevent React from auto-opening browser
    env = os.environ.copy()
    env['BROWSER'] = 'none'
    
    react_process = subprocess.Popen(
        ['cmd', '/c', 'npm', 'start'],
        cwd=str(FRONTEND_DIR),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )
    
    print(f"React started (PID: {react_process.pid})")
    return react_process

def wait_for_server(url, max_attempts=30):
    """Wait for server to be ready"""
    import urllib.request
    
    for i in range(max_attempts):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except:
            time.sleep(1)
    return False

def check_port_active(port):
    """Check if there are active connections to a port"""
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.status == 'ESTABLISHED':
            return True
    return False

def monitor_and_cleanup(flask_pid, react_pid):
    """Monitor browser activity and cleanup when browser closes"""
    print("Monitoring browser activity...")
    
    no_activity_count = 0
    max_no_activity = 12  # 60 seconds of no activity
    
    while True:
        time.sleep(5)
        
        # Check if port 3000 has active connections
        port_active = check_port_active(3000)
        
        if not port_active:
            no_activity_count += 1
            print(f"No browser activity detected ({no_activity_count}/{max_no_activity})")
        else:
            no_activity_count = 0
        
        # If no activity for too long, shutdown servers
        if no_activity_count >= max_no_activity:
            print("Browser appears closed. Shutting down servers...")
            
            # Kill all related processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'app.py' in cmdline or ('node' in proc.info['name'].lower() and 'react-scripts' in cmdline):
                        proc.kill()
                        print(f"Killed: {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            print("Cleanup complete. Exiting.")
            break

def main():
    """Main entry point"""
    print("=" * 60)
    print("CRM Log Summary Dashboard - Hidden Server Launcher")
    print("=" * 60)
    
    # Kill any existing servers
    kill_existing_servers()
    time.sleep(1)
    
    # Start servers
    flask_proc = start_flask_server()
    time.sleep(4)
    
    react_proc = start_react_server()
    
    # Wait for servers to be ready
    print("\nWaiting for Flask backend to be ready...")
    if wait_for_server('http://localhost:5000/api/health', max_attempts=15):
        print("[OK] Flask backend is ready")
    else:
        print("[FAIL] Flask backend failed to start")
        return
    
    print("\nWaiting for React frontend to be ready...")
    if wait_for_server('http://localhost:3000', max_attempts=30):
        print("[OK] React frontend is ready")
    else:
        print("[FAIL] React frontend failed to start")
        return
    
    # Open browser
    print("\nOpening browser...")
    webbrowser.open('http://localhost:3000')
    
    # Start monitoring
    print("\n" + "=" * 60)
    print("Dashboard is running!")
    print("Close the browser tab to automatically shutdown servers.")
    print("=" * 60 + "\n")
    
    try:
        monitor_and_cleanup(flask_proc.pid, react_proc.pid)
    except KeyboardInterrupt:
        print("\nManual shutdown requested...")
        kill_existing_servers()

if __name__ == '__main__':
    main()
