# Winmark Corporation Onboarding Guide

A modern onboarding application for new hires at Winmark Corporation, featuring an interactive FAQ chatbot and integrated company address book.

## Features

- **Welcome Page** — Company overview and quick-start navigation
- **First Day & Week** — Day-by-day schedule for your first week
- **IT & Technology** — Email, VPN, software setup guides
- **HR & Benefits** — PTO, insurance, payroll, dress code info
- **Facilities** — Office location, parking, break room, key contacts
- **Address Book** — Embedded Winmark Phone Directory
- **Onboarding Checklist** — Interactive progress tracker (saved locally)
- **FAQ Chatbot** — Rule-based assistant for common onboarding questions

## Tech Stack

- **Frontend:** React + Vite + TailwindCSS + Lucide Icons
- **Backend:** Flask + Flask-CORS
- **Chatbot:** Keyword-matching FAQ engine (no API key required)

## Quick Start

### Option 1: Use the startup script
```
Double-click start.bat
```

### Option 2: Manual startup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python app.py
```

**Frontend (in a separate terminal):**
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000 in your browser.

## Project Structure

```
OnboardingGuide/
├── backend/
│   ├── app.py              # Flask API server
│   ├── faq_data.py         # FAQ knowledge base
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AddressBook.jsx
│   │   │   ├── ChatBot.jsx
│   │   │   ├── Checklist.jsx
│   │   │   ├── Facilities.jsx
│   │   │   ├── FirstDayWeek.jsx
│   │   │   ├── HRBenefits.jsx
│   │   │   ├── ITSetup.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   └── Welcome.jsx
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── vite.config.js
├── start.bat
└── README.md
```

## Customization

### Adding FAQ entries
Edit `backend/faq_data.py` to add new Q&A pairs. Each entry needs:
- `keywords` — List of words/phrases that trigger this answer
- `question` — The canonical question text
- `answer` — The response (supports Markdown formatting)

### Modifying the checklist
Edit the `INITIAL_CHECKLIST` array in `frontend/src/components/Checklist.jsx`.

## Address Book Integration

The app embeds the Winmark Phone Directory from https://addressbook.winmarkcorporation.com via iframe, with a direct link fallback.
