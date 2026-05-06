@echo off
echo Starting CRM Log Summary Dashboard...
echo.

echo Starting Flask Backend...
start "Flask Backend" cmd /k "cd backend && python app.py"

timeout /t 3 /nobreak >nul

echo Starting React Frontend...
start "React Frontend" cmd /k "cd frontend && npm start"

echo.
echo Both servers are starting...
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo.
echo Press any key to exit this window (servers will continue running)...
pause >nul
