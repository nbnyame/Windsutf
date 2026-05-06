import psutil
import time
import subprocess
import sys
import os
from pathlib import Path

def find_process_by_cmdline(search_term):
    """Find processes matching a command line search term"""
    matching_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(search_term in ' '.join(cmdline) for search_term in [search_term]):
                matching_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return matching_pids

def kill_server_processes():
    """Kill Flask and Node.js server processes"""
    killed = []
    
    # Kill Node.js processes (React dev server)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'node.exe':
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'react-scripts' in cmdline or 'npm' in cmdline:
                    proc.kill()
                    killed.append(f"Node.js (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Kill Flask processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python.exe':
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'app.py' in cmdline:
                    proc.kill()
                    killed.append(f"Flask (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return killed

def check_port_in_use(port):
    """Check if a port is being actively used"""
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.status == 'ESTABLISHED':
            return True
    return False

def monitor_browser_activity():
    """Monitor if browser is still accessing the app"""
    print("Starting browser activity monitor...")
    
    # Wait for servers to fully start
    time.sleep(10)
    
    # Monitor for activity
    no_activity_count = 0
    max_no_activity = 12  # 12 * 5 seconds = 60 seconds of no activity
    
    while True:
        time.sleep(5)
        
        # Check if port 3000 has active connections
        port_active = check_port_in_use(3000)
        
        # Check if React dev server is still running
        react_running = any('node.exe' in p.name() for p in psutil.process_iter(['name']))
        
        # Check if Flask is still running
        flask_running = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] == 'python.exe':
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'app.py' in cmdline:
                        flask_running = True
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # If servers are not running, exit
        if not react_running and not flask_running:
            print("Servers already stopped. Exiting monitor.")
            break
        
        # If no active connections to port 3000, increment counter
        if not port_active:
            no_activity_count += 1
            print(f"No activity detected ({no_activity_count}/{max_no_activity})")
        else:
            no_activity_count = 0
            print("Activity detected, resetting counter")
        
        # If no activity for too long, assume browser closed
        if no_activity_count >= max_no_activity:
            print("Browser appears to be closed. Shutting down servers...")
            killed = kill_server_processes()
            print(f"Killed processes: {killed}")
            break

if __name__ == '__main__':
    try:
        monitor_browser_activity()
    except KeyboardInterrupt:
        print("\nMonitor interrupted. Cleaning up...")
        kill_server_processes()
    except Exception as e:
        print(f"Error in monitor: {e}")
        kill_server_processes()
