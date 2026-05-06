# Setup Instructions for CRM Log Summary Dashboard

## ✅ Backend Setup (COMPLETED)
The Flask backend is already running on http://localhost:5000

## Frontend Setup (Action Required)

You need to install the frontend dependencies. Due to PowerShell execution policy, you have two options:

### Option 1: Enable PowerShell Scripts (Recommended)
Run this command in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run:
```bash
cd Dynamics365CRM\LogSummaryApp\frontend
npm install
npm start
```

### Option 2: Use Command Prompt Instead
Open Command Prompt (cmd.exe) and run:
```bash
cd c:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp\frontend
npm install
npm start
```

### Option 3: Use the Batch File
Simply double-click on `start_app.bat` in the LogSummaryApp folder. This will:
- Start the Flask backend (if not already running)
- Install frontend dependencies (if needed)
- Start the React frontend

## Quick Start (Easiest Method)

1. **Stop the current Flask server** (press Ctrl+C in the terminal where it's running)
2. **Double-click** `start_app.bat` in the `LogSummaryApp` folder
3. Wait for both servers to start
4. Open your browser to http://localhost:3000

## What You'll See

The dashboard displays:
- **Total Statistics**: Cases created, DRS updates, and errors
- **Recent Events**: Last 100 events from both log files
- **Filtering**: View all events or filter by type (Cases, DRS Updates, Errors)
- **Auto-Refresh**: Updates every 30 seconds (can be toggled off)
- **Beautiful UI**: Modern gradient design with smooth animations

## Features

✨ **Case Tracking**: See all new cases created with store numbers and case IDs
✨ **DRS Monitoring**: Track DRS version updates with store info and account names
✨ **Error Alerts**: Quickly identify and review errors from the polling process
✨ **Real-time Updates**: Auto-refresh keeps you informed of new events
✨ **Responsive Design**: Works on desktop and mobile devices
