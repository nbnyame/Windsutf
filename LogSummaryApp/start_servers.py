"""
CRM Log Summary Dashboard - Browser Launcher
Opens the dashboard in the default browser.
The backend runs permanently via Windows Task Scheduler (start_backend_hidden.vbs).
"""
import webbrowser

if __name__ == '__main__':
    webbrowser.open('http://localhost:5000')
