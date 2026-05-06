# CRM Log Summary Dashboard

A modern web application to monitor and summarize CRM case creation and DRS update logs.

## Features

- **Real-time Monitoring**: Auto-refreshes every 30 seconds
- **Case Tracking**: View all new cases created from SharePoint
- **DRS Updates**: Monitor Splunk DRS version updates
- **Error Tracking**: See all errors from the polling process
- **Beautiful UI**: Modern, responsive design with smooth animations
- **Filtering**: Filter events by type (All, Cases, DRS Updates, Errors)

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd Dynamics365CRM\LogSummaryApp\backend
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Start the Flask backend:
   ```
   python app.py
   ```
   The backend will run on http://localhost:5000

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd Dynamics365CRM\LogSummaryApp\frontend
   ```

2. Install Node.js dependencies:
   ```
   npm install
   ```

3. Start the React development server:
   ```
   npm start
   ```
   The frontend will run on http://localhost:3000

## Usage

1. Make sure both backend and frontend are running
2. Open your browser to http://localhost:3000
3. The dashboard will automatically load and display:
   - Total counts of cases, DRS updates, and errors
   - Recent events (last 100)
   - Ability to filter by event type
   - Auto-refresh every 30 seconds (can be toggled off)

## Log Files

The app monitors these log files:
- `poller.log` - SharePoint to CRM case creation events
- `drs_poller.log` - Splunk DRS version updates

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: React
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **Styling**: Custom CSS with modern gradients
