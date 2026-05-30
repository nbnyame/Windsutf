import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  FileText, 
  Database, 
  AlertCircle, 
  RefreshCw, 
  CheckCircle,
  Clock,
  Store,
  Package,
  Calendar,
  RotateCcw,
  Inbox,
  Zap
} from 'lucide-react';
import './App.css';

function App() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('case_created');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [events, setEvents] = useState([]);

  const fetchSummary = async () => {
    try {
      const response = await axios.get('/api/summary');
      setSummary(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch log data. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEventsByDate = async (date) => {
    try {
      let response;
      if (activeTab === 'case_created') {
        response = await axios.get(`/api/cases?date=${date}`);
      } else if (activeTab === 'drs_update') {
        response = await axios.get(`/api/drs-updates?date=${date}`);
      } else if (activeTab === 'duplicate_increment') {
        response = await axios.get(`/api/duplicates?date=${date}`);
      } else if (activeTab === 'error') {
        response = await axios.get(`/api/errors?date=${date}`);
      } else if (activeTab === 'retry') {
        response = await axios.get(`/api/retries?date=${date}`);
      } else if (activeTab === 'splunk') {
        response = await axios.get(`/api/splunk-alerts?date=${date}`);
      }
      setEvents(response.data);
    } catch (err) {
      console.error('Failed to fetch events:', err);
      setEvents([]);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  useEffect(() => {
    fetchEventsByDate(selectedDate);
  }, [activeTab, selectedDate]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchSummary();
        fetchEventsByDate(selectedDate);
      }, 15000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedDate, activeTab]);

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getEventIcon = (type) => {
    switch (type) {
      case 'case_created':
        return <FileText className="event-icon case" />;
      case 'drs_update':
        return <Database className="event-icon drs" />;
      case 'duplicate_increment':
        return <RefreshCw className="event-icon duplicate" />;
      case 'error':
        return <AlertCircle className="event-icon error" />;
      case 'retry':
        return <RotateCcw className="event-icon retry" />;
      case 'splunk':
        return <Zap className="event-icon splunk" />;
      default:
        return <Clock className="event-icon" />;
    }
  };

  const handleDateChange = (e) => {
    setSelectedDate(e.target.value);
  };

  const getTodayDate = () => {
    return new Date().toISOString().split('T')[0];
  };

  const isTimeDifferenceOverOneHour = (timeDiff) => {
    if (!timeDiff) return false;
    // Parse time difference like "0:05:15" or "1:30:00" or "17:55:40"
    const parts = timeDiff.split(':');
    if (parts.length < 2) return false;
    const hours = parseInt(parts[0]);
    return hours >= 1;
  };

  const renderEventCard = (event, index) => {
    return (
      <div key={index} className={`event-card ${event.type}`}>
        <div className="event-header">
          {getEventIcon(event.type)}
          <span className="event-time">{formatTimestamp(event.timestamp)}</span>
        </div>
        <div className="event-content">
          {event.type === 'case_created' && (
            <>
              <div className="event-detail">
                <Store size={16} />
                <span><strong>Store: {event.store}</strong></span>
              </div>
              {event.account && event.account.toLowerCase() !== 'staff' && (
                <div className="event-detail account-name">
                  <span>Contact: {event.account}</span>
                </div>
              )}
              <div className="event-detail case-summary">
                <span>Subject: {event.subject}</span>
              </div>
              <div className="event-detail case-summary">
                <span>Case Type: {event.case_type}</span>
              </div>
              {event.time_difference && (
                <div className={`event-detail time-difference ${isTimeDifferenceOverOneHour(event.time_difference) ? 'over-one-hour' : ''}`}>
                  <Clock size={16} />
                  <span>Time Difference: {event.time_difference}</span>
                </div>
              )}
              <div className="event-detail email-verification">
                {event.email_verified ? (
                  <>
                    <span className="email-check">✓</span>
                    <span>Email Verified</span>
                  </>
                ) : (
                  <>
                    <span className="email-x">✗</span>
                    <span>Email Not Found</span>
                  </>
                )}
              </div>
              {event.draft_status && (
                <div className="event-detail draft-status">
                  {event.draft_status === 'moved' ? (
                    <>
                      <span className="draft-check">✓</span>
                      <span>Draft Reply Moved</span>
                    </>
                  ) : event.draft_status === 'not_found' ? (
                    <>
                      <span className="draft-x">✗</span>
                      <span>No Draft Found</span>
                    </>
                  ) : null}
                </div>
              )}
              <div className="event-detail case-status">
                <span className="status-badge">{event.status}</span>
              </div>
            </>
          )}
          {event.type === 'drs_update' && (
            <>
              <div className="event-detail">
                <Store size={16} />
                <span><strong>Store:</strong> {event.store}</span>
              </div>
              <div className="event-detail">
                <span><strong>Account:</strong> {event.account}</span>
              </div>
              <div className="event-detail">
                <Package size={16} />
                <span><strong>DRS Version:</strong> {event.drs_version}</span>
              </div>
            </>
          )}
          {event.type === 'duplicate_increment' && (
            <>
              <div className="event-detail">
                <Store size={16} />
                <span><strong>Store: {event.store}</strong></span>
              </div>
              {event.account && event.account.toLowerCase() !== 'staff' && (
                <div className="event-detail account-name">
                  <span>Contact: {event.account}</span>
                </div>
              )}
              <div className="event-detail case-summary">
                <span>Subject: {event.subject}</span>
              </div>
              <div className="event-detail case-summary">
                <span>Case Type: {event.case_type}</span>
              </div>
              <div className="event-detail case-summary">
                <span>{event.is_increment ? 'Increment' : 'Duplicate'} Type: {event.duplicate_type}</span>
              </div>
              <div className="event-detail case-status">
                <span className="status-badge">{event.status}</span>
              </div>
            </>
          )}
          {event.type === 'error' && (
            <div className="error-message">
              {event.message}
            </div>
          )}
          {event.type === 'retry' && (
            <>
              {event.action === 'moved_to_retry' && (
                <>
                  <div className="event-detail retry-action retry-stage1">
                    <RotateCcw size={16} />
                    <span>Moved to Retry subfolder</span>
                  </div>
                  <div className="event-detail retry-subject">
                    <span>{event.subject}</span>
                  </div>
                  <div className="event-detail retry-duration">
                    <Clock size={14} />
                    <span>In folder for {event.duration}</span>
                  </div>
                </>
              )}
              {event.action === 'moved_to_retry2' && (
                <>
                  <div className="event-detail retry-action retry-stage2">
                    <RotateCcw size={16} />
                    <span>Moved to Retry 2 subfolder</span>
                  </div>
                  <div className="event-detail retry-subject">
                    <span>{event.subject}</span>
                  </div>
                  <div className="event-detail retry-duration">
                    <Clock size={14} />
                    <span>In folder for {event.duration}</span>
                  </div>
                </>
              )}
              {event.action === 'moved_to_inbox' && (
                <>
                  <div className="event-detail retry-action retry-stage3">
                    <Inbox size={16} />
                    <span>Escalated to Inbox (manual handling)</span>
                  </div>
                  <div className="event-detail retry-subject">
                    <span>{event.subject}</span>
                  </div>
                  <div className="event-detail retry-duration">
                    <Clock size={14} />
                    <span>In folder for {event.duration}</span>
                  </div>
                </>
              )}
              {event.action === 'error' && (
                <div className="error-message">
                  {event.message}
                </div>
              )}
            </>
          )}
          {event.type === 'splunk' && (
            <>
              {event.email_type === 'error' ? (
                <div className="error-message">{event.message}</div>
              ) : (
                <>
                  <div className="splunk-badges">
                    <span className={`splunk-type-badge ${event.email_type}`}>
                      {event.email_type === 'cf_late' ? 'CF Late' : 'Non-Start Point'}
                    </span>
                    {event.test_mode && <span className="splunk-test-badge">TEST MODE</span>}
                  </div>
                  <div className="event-detail splunk-subject">
                    <span>{event.subject}</span>
                  </div>
                  <div className="splunk-stats">
                    <span className="splunk-stat created">{event.cases_created.length} created</span>
                    {event.cases_failed.length > 0 && <span className="splunk-stat failed">{event.cases_failed.length} failed</span>}
                    {event.cases_skipped.length > 0 && <span className="splunk-stat skipped">{event.cases_skipped.length} duplicate{event.cases_skipped.length !== 1 ? 's' : ''}</span>}
                    {event.stores_below_threshold.length > 0 && <span className="splunk-stat threshold">{event.stores_below_threshold.length} below threshold</span>}
                  </div>
                  {event.cases_created.length > 0 && (
                    <div className="splunk-store-list">
                      {event.cases_created.map((c, i) => (
                        <div key={i} className="splunk-store-row created">
                          <span className="splunk-check">✓</span>
                          <span>Store {c.store}: {c.ticket}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {event.cases_failed.length > 0 && (
                    <div className="splunk-store-list">
                      {event.cases_failed.map((c, i) => (
                        <div key={i} className="splunk-store-row failed">
                          <span className="splunk-x">✗</span>
                          <span>{c.store ? `Store ${c.store}: ` : ''}{c.error}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {event.destination && (
                    <div className="event-detail splunk-destination">
                      <span className={`splunk-dest-badge ${event.destination.includes('fallback') ? 'fallback' : ''}`}>
                        → {event.destination}
                      </span>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="loading-container">
        <RefreshCw className="loading-spinner" size={48} />
        <p>Loading log data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <AlertCircle size={48} />
        <p>{error}</p>
        <button onClick={fetchSummary} className="retry-button">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>CRM Log Summary Dashboard</h1>
        <div className="header-controls">
          <button 
            onClick={fetchSummary} 
            className="refresh-button"
            title="Refresh now"
          >
            <RefreshCw size={20} />
          </button>
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh (15s)
          </label>
        </div>
      </header>

      <div className="stats-container">
        <div className="stat-card cases">
          <FileText size={32} />
          <div className="stat-content">
            <h3>{summary?.total_cases || 0}</h3>
            <p>Cases Created Today</p>
          </div>
        </div>
        <div className="stat-card drs">
          <Database size={32} />
          <div className="stat-content">
            <h3>{summary?.total_drs_updates || 0}</h3>
            <p>DRS Updates Today</p>
          </div>
        </div>
        <div className="stat-card duplicates">
          <AlertCircle size={32} />
          <div className="stat-content">
            <h3>{summary?.total_duplicates || 0}</h3>
            <p>Duplicates Today</p>
          </div>
        </div>
        <div className="stat-card increments">
          <RefreshCw size={32} />
          <div className="stat-content">
            <h3>{summary?.total_increments || 0}</h3>
            <p>Increments Today</p>
          </div>
        </div>
      </div>

      <div className="tabs">
        <button 
          className={activeTab === 'case_created' ? 'active' : ''}
          onClick={() => setActiveTab('case_created')}
        >
          Cases Created
        </button>
        <button 
          className={activeTab === 'drs_update' ? 'active' : ''}
          onClick={() => setActiveTab('drs_update')}
        >
          DRS Updates
        </button>
        <button 
          className={activeTab === 'duplicate_increment' ? 'active' : ''}
          onClick={() => setActiveTab('duplicate_increment')}
        >
          Duplicates/Increments
        </button>
        <button 
          className={activeTab === 'error' ? 'active' : ''}
          onClick={() => setActiveTab('error')}
        >
          Errors
        </button>
        <button 
          className={activeTab === 'retry' ? 'active' : ''}
          onClick={() => setActiveTab('retry')}
        >
          Retries
        </button>
        <button 
          className={activeTab === 'splunk' ? 'active' : ''}
          onClick={() => setActiveTab('splunk')}
        >
          Splunk Alerts
        </button>
      </div>

      {(activeTab === 'case_created' || activeTab === 'drs_update' || activeTab === 'duplicate_increment' || activeTab === 'error' || activeTab === 'retry' || activeTab === 'splunk') && (
        <div className="date-picker-container">
          <Calendar size={20} className="calendar-icon" />
          <input 
            type="date" 
            value={selectedDate}
            onChange={handleDateChange}
            max={getTodayDate()}
            className="date-picker"
          />
          <span className="date-label">
            {selectedDate === getTodayDate() ? 'Today' : selectedDate}
          </span>
          {(activeTab === 'case_created' || activeTab === 'drs_update') && (
            <span className="date-count">
              {events.length} {activeTab === 'case_created' ? 'case' : 'update'}{events.length !== 1 ? 's' : ''}
            </span>
          )}
          {activeTab === 'duplicate_increment' && (
            <>
              <span className="date-count duplicates-count">
                {events.filter(e => !e.is_increment).length} duplicate{events.filter(e => !e.is_increment).length !== 1 ? 's' : ''}
              </span>
              <span className="date-count increments-count">
                {events.filter(e => e.is_increment).length} increment{events.filter(e => e.is_increment).length !== 1 ? 's' : ''}
              </span>
            </>
          )}
        </div>
      )}

      <div className="events-container">
        {events.length === 0 ? (
          <div className="no-events">
            <p>No events found for {selectedDate === getTodayDate() ? 'today' : selectedDate}</p>
          </div>
        ) : (
          events.map((event, index) => renderEventCard(event, index))
        )}
      </div>

      <footer className="app-footer">
        <p>Last updated: {summary?.last_updated ? formatTimestamp(summary.last_updated) : 'Never'}</p>
      </footer>
    </div>
  );
}

export default App;
