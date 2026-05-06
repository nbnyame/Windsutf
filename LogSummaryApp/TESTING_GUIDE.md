# CRM Log Summary Dashboard - Testing Guide

## 🧪 Testing Workflow

This guide documents the testing procedure to run after every change to the dashboard.

## ✅ Current Test Results (Last Run: 2026-05-05)

### Backend API Tests
- ✅ `/api/health` - Returns status: healthy, both log files exist
- ✅ `/api/summary` - Returns aggregated data with total counts and recent events
- ✅ `/api/cases` - Returns case creation events (50 most recent)
- ✅ `/api/drs-updates` - Returns DRS version updates (50 most recent)
- ✅ `/api/errors` - Returns error events from logs (50 most recent)

### Frontend Tests
- ✅ React dev server starts successfully on http://localhost:3000
- ✅ Dependencies installed correctly (node_modules present)
- ✅ Webpack compilation successful
- ✅ Dashboard accessible in browser

## 📋 Testing Checklist

### 1. Backend API Testing

Start the Flask backend:
```bash
cd backend
python app.py
```

Test all endpoints:
```bash
# Health check
curl http://localhost:5000/api/health

# Summary endpoint
curl http://localhost:5000/api/summary

# Cases endpoint
curl http://localhost:5000/api/cases

# DRS updates endpoint
curl http://localhost:5000/api/drs-updates

# Errors endpoint
curl http://localhost:5000/api/errors
```

**Expected Results:**
- All endpoints return HTTP 200
- JSON responses are properly formatted
- Data is being parsed from log files correctly
- CORS headers are present

### 2. Frontend Testing

Start the React frontend:
```bash
cd frontend
npm start
```

**Manual Browser Tests:**
1. Open http://localhost:3000
2. Verify dashboard loads without errors
3. Check that statistics cards show correct counts
4. Verify recent events are displayed
5. Test tab filtering (All, Cases, DRS Updates, Errors)
6. Verify auto-refresh toggle works
7. Click refresh button to manually refresh
8. Check that timestamps are formatted correctly
9. Verify color coding (green for cases, blue for DRS, red for errors)

### 3. Data Parsing Tests

**Verify log parsing:**
- Cases show: timestamp, store number, case ID
- DRS updates show: timestamp, store number, account name, DRS version
- Errors show: timestamp, error message

**Check data accuracy:**
- Compare a few entries with actual log files
- Verify timestamps are parsed correctly
- Ensure store numbers match

### 4. Integration Tests

**Full workflow test:**
1. Stop both servers
2. Run `launch_app_hidden.vbs` (or desktop shortcut)
3. Verify both servers start in minimized windows
4. Verify browser opens automatically
5. Verify dashboard loads with data
6. Close browser tab
7. Wait 60 seconds
8. Verify servers auto-shutdown

## 🔧 Common Issues & Solutions

### Issue: "react-scripts not found"
**Solution:** Run `install_dependencies.bat` or `npm install` in frontend folder

### Issue: "Cannot connect to localhost:3000"
**Solution:** 
1. Check if React dev server is running
2. Verify npm dependencies are installed
3. Check for port conflicts

### Issue: "No data showing in dashboard"
**Solution:**
1. Verify log files exist at correct paths
2. Check Flask backend is running
3. Test API endpoints directly
4. Check browser console for errors

### Issue: "CORS errors in browser"
**Solution:** Verify flask-cors is installed and configured in backend/app.py

## 🚀 Quick Test Script

For rapid testing after changes, use this command sequence:

```bash
# Terminal 1 - Backend
cd backend && python app.py

# Terminal 2 - Frontend  
cd frontend && npm start

# Terminal 3 - API Tests
curl http://localhost:5000/api/health
curl http://localhost:5000/api/summary
```

Then open http://localhost:3000 in browser.

## 📊 Test Data Validation

The dashboard should display:
- **Cases**: Store numbers, case IDs, timestamps
- **DRS Updates**: Store numbers, account names, DRS versions
- **Errors**: Error messages with timestamps
- **Counts**: Accurate totals for each category

## 🔄 After Making Changes

1. **Backend changes** (app.py, parsing logic):
   - Restart Flask server
   - Test all API endpoints
   - Verify data parsing is correct

2. **Frontend changes** (React components, CSS):
   - React will auto-reload
   - Check browser console for errors
   - Test all UI interactions

3. **Dependency changes**:
   - Run `npm install` or `pip install`
   - Restart both servers
   - Full integration test

## ✅ Sign-off Checklist

Before confirming changes are complete:
- [ ] All API endpoints return 200
- [ ] Dashboard loads without errors
- [ ] Data displays correctly
- [ ] Filtering works
- [ ] Auto-refresh works
- [ ] Desktop shortcut launches successfully
- [ ] Auto-cleanup works when browser closes
- [ ] No console errors in browser
- [ ] No Python errors in backend
