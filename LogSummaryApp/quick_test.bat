@echo off
echo ============================================================
echo CRM Log Summary Dashboard - Quick Test
echo ============================================================
echo.

echo Testing Backend API...
echo.

echo [1/5] Health Check...
curl -s http://localhost:5000/api/health
echo.
echo.

echo [2/5] Summary Endpoint...
curl -s http://localhost:5000/api/summary | findstr "total_cases total_drs_updates total_errors"
echo.
echo.

echo [3/5] Cases Endpoint...
curl -s http://localhost:5000/api/cases | findstr "case_id"
echo.
echo.

echo [4/5] DRS Updates Endpoint...
curl -s http://localhost:5000/api/drs-updates | findstr "drs_version"
echo.
echo.

echo [5/5] Errors Endpoint...
curl -s http://localhost:5000/api/errors | findstr "message"
echo.
echo.

echo ============================================================
echo Test Complete!
echo ============================================================
echo.
echo If all tests showed data, the backend is working correctly.
echo Open http://localhost:3000 to test the frontend.
echo.
pause
