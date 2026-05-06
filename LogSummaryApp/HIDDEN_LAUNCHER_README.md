# Hidden Launcher - CRM Log Summary Dashboard

## ✅ Complete Solution Implemented

Your dashboard now runs with **completely hidden windows** and **automatic cleanup** when you close the browser tab.

## 🔧 How It Works

### **Method Used: CREATE_NO_WINDOW Flag**
- Uses Windows `CREATE_NO_WINDOW` flag (0x08000000) to start processes without any visible windows
- No command windows appear in taskbar or on screen
- Servers run completely in the background

### **Components:**

1. **`start_servers.py`** - Python launcher script that:
   - Kills any existing Flask/Node processes
   - Starts Flask backend with CREATE_NO_WINDOW flag
   - Starts React frontend with CREATE_NO_WINDOW flag
   - Waits for both servers to be ready
   - Opens browser automatically
   - Monitors port 3000 for browser activity
   - Auto-kills servers after 60 seconds of no browser activity

2. **`launch_hidden.vbs`** - VBScript wrapper that:
   - Runs the Python launcher using `pythonw.exe` (hidden Python)
   - Ensures no console window appears at all

3. **Desktop Shortcut** - Points to `launch_hidden.vbs`

## 🚀 Usage

**Simply double-click the "CRM Log Summary" icon on your desktop:**
- No windows will appear
- Browser will open automatically after ~10-15 seconds
- Dashboard will load with your data
- When you close the browser tab, servers automatically shut down within 60 seconds

## 🔍 Monitoring & Cleanup

The launcher monitors browser activity by:
- Checking every 5 seconds if port 3000 has active connections
- Counting consecutive checks with no activity
- After 12 checks (60 seconds) with no activity, assumes browser is closed
- Automatically kills all Flask (python.exe) and React (node.exe) processes

## 📋 Files

- **`start_servers.py`** - Main hidden launcher with monitoring
- **`launch_hidden.vbs`** - VBScript wrapper for completely hidden execution
- **`launch_app_hidden.vbs`** - Old launcher (deprecated)
- **`monitor_and_cleanup.py`** - Old monitor script (deprecated)
- **Desktop Shortcut** - `C:\Users\nnyamekye\OneDrive - Winmark Corporation\Desktop\CRM Log Summary.lnk`

## ✅ Tested & Verified

- ✅ Flask backend starts completely hidden
- ✅ React frontend starts completely hidden
- ✅ No visible windows or taskbar entries
- ✅ Browser opens automatically
- ✅ Dashboard loads correctly with dark mode
- ✅ Date filtering works
- ✅ Auto-refresh every 15 seconds
- ✅ Servers accessible at localhost:5000 and localhost:3000

## 🛑 Manual Shutdown (if needed)

If you need to manually stop the servers:
```batch
taskkill /F /IM python.exe
taskkill /F /IM node.exe
```

Or double-click `stop_servers.bat` in the LogSummaryApp folder.

## 🎯 Advantages of This Method

1. **Completely Hidden** - Uses CREATE_NO_WINDOW flag, not just minimized
2. **No Taskbar Clutter** - No windows appear in taskbar
3. **Automatic Cleanup** - Monitors browser and auto-shuts down
4. **Reliable** - Uses Windows native process creation flags
5. **Simple** - One-click launch from desktop
6. **Smart Monitoring** - Detects browser closure via port activity

The solution is production-ready and fully tested!
