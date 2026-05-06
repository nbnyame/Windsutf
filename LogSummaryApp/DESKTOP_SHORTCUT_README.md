# Desktop Shortcut - CRM Log Summary Dashboard

## ✅ Shortcut Created!

A desktop shortcut named **"CRM Log Summary"** has been created on your desktop.

## ⚠️ First Time Setup

**Before using the desktop shortcut for the first time**, you must install dependencies:

1. Navigate to the LogSummaryApp folder
2. Double-click `first_time_setup.bat`
3. Wait for all dependencies to install
4. Setup is complete!

This only needs to be done once.

## 🚀 How to Use

Simply **double-click** the "CRM Log Summary" icon on your desktop and the app will:

1. ✅ Start the Flask backend server (http://localhost:5000) - **HIDDEN**
2. ✅ Start the React frontend server (http://localhost:3000) - **HIDDEN**
3. ✅ Automatically open the dashboard in your default browser
4. ✅ Show a notification when everything is ready
5. ✅ Monitor browser activity and auto-cleanup when you close the tab

## 📝 What Happens When You Click

- **No command windows will appear** - servers run completely hidden in the background
- After a few seconds, your browser will open to http://localhost:3000
- A notification will confirm the app is starting
- A background monitor watches for when you close the browser tab

## 🛑 How to Stop the App

**Automatic Cleanup:**
- Simply **close the browser tab** - the servers will automatically shut down within 60 seconds

**Manual Stop (if needed):**
- Double-click `stop_servers.bat` in the LogSummaryApp folder
- This will immediately kill all Flask and Node.js processes

## 🔧 Recreating the Shortcut

If you ever need to recreate the desktop shortcut:

**Option 1:** Double-click `create_desktop_shortcut.bat` in this folder

**Option 2:** Run this PowerShell command:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp\create_desktop_shortcut.ps1"
```

## 📂 Files Created

- **launch_app_hidden.vbs** - VBScript that launches both servers hidden and opens browser
- **monitor_and_cleanup.py** - Python script that monitors browser activity and auto-kills servers
- **stop_servers.bat** - Manual script to stop all servers immediately
- **create_desktop_shortcut.ps1** - PowerShell script to create the shortcut
- **create_desktop_shortcut.bat** - Batch file wrapper for the PowerShell script
- **Desktop Shortcut** - Located at: `C:\Users\nnyamekye\OneDrive - Winmark Corporation\Desktop\CRM Log Summary.lnk`

## 💡 Tips

- The app will auto-refresh every 30 seconds to show new log entries
- You can toggle auto-refresh off if you prefer manual updates
- The dashboard shows the last 100 events from both log files
- Use the filter tabs to view only Cases, DRS Updates, or Errors

## 🔍 How Auto-Cleanup Works

The monitor script (`monitor_and_cleanup.py`) runs in the background and:
- Checks every 5 seconds if the browser is still accessing port 3000
- If no activity is detected for 60 seconds, it assumes the browser tab is closed
- Automatically kills both Flask (Python) and React (Node.js) server processes
- Runs completely hidden - you won't see any windows or notifications

## ⚙️ Technical Details

- **Backend**: Flask server runs on port 5000 (hidden)
- **Frontend**: React dev server runs on port 3000 (hidden)
- **Monitor**: Python script using `psutil` library to track processes and network connections
- **Cleanup**: Gracefully terminates server processes when browser closes
