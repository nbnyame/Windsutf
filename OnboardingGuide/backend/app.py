import os
import sys
import time
import threading
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from faq_data import FAQ_ENTRIES
from employee_lookup import detect_employee_query, search_employees, format_employee_list, fetch_employees

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# ---- Heartbeat / graceful shutdown ----
_last_heartbeat = time.time()
_HEARTBEAT_TIMEOUT = 10  # seconds with no heartbeat before auto-shutdown


def find_best_answer(user_message: str) -> dict:
    """Match user message against FAQ entries using keyword scoring."""
    message_lower = user_message.lower().strip()

    if not message_lower:
        return {
            "question": "Empty message",
            "answer": "It looks like you sent an empty message. Try asking me about company info, IT setup, HR policies, or anything onboarding-related!",
            "confidence": 0,
        }

    best_match = None
    best_score = 0

    for entry in FAQ_ENTRIES:
        score = 0
        for keyword in entry["keywords"]:
            keyword_lower = keyword.lower()
            if keyword_lower in message_lower:
                # Longer keyword matches are weighted higher
                score += len(keyword_lower.split())

        if score > best_score:
            best_score = score
            best_match = entry

    if best_match and best_score > 0:
        return {
            "question": best_match["question"],
            "answer": best_match["answer"],
            "confidence": min(best_score / 3.0, 1.0),
        }

    return {
        "question": user_message,
        "answer": (
            "I'm not sure about that one! Here are some things I can help with:\n"
            "• **Company info** – Ask about Winmark, our brands, or mission\n"
            "• **First day/week** – What to expect when you start\n"
            "• **IT setup** – Email, VPN, software, passwords\n"
            "• **Benefits & HR** – PTO, insurance, payroll, dress code\n"
            "• **Facilities** – Parking, break room, office hours\n"
            "• **Address Book** – Find coworker contact information\n"
            "• **Training** – Learning and development opportunities\n\n"
            "Try rephrasing your question or ask about one of these topics!"
        ),
        "confidence": 0,
    }


@app.route("/")
def index():
    """Serve the main onboarding guide page."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages from the frontend."""
    data = request.get_json()
    user_message = data.get("message", "")

    # Check for employee/department lookup first
    search_term = detect_employee_query(user_message)
    if search_term:
        employees = search_employees(search_term)
        reply = format_employee_list(employees)
        if reply:
            return jsonify({"reply": reply, "matched_question": user_message})
        return jsonify({
            "reply": f'I couldn\'t find anyone matching "{search_term}". Try searching by first name, last name, or department (e.g., "Who is in Technology?" or "Find John Smith").',
            "matched_question": user_message,
        })

    result = find_best_answer(user_message)
    return jsonify({"reply": result["answer"], "matched_question": result["question"]})


@app.route("/api/faq", methods=["GET"])
def get_faq():
    """Return a list of common questions for quick-access buttons."""
    common_questions = [
        "What should I expect on my first day?",
        "How do I set up my email?",
        "What is the PTO policy?",
        "What benefits does Winmark offer?",
        "How do I connect to the VPN?",
        "Where do I park?",
        "What is the dress code?",
        "How do I find a coworker's contact info?",
        "What training opportunities are available?",
        "Who should I contact for help?",
    ]
    return jsonify({"questions": common_questions})


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    """Browser sends this periodically so the server knows it's still open."""
    global _last_heartbeat
    _last_heartbeat = time.time()
    return jsonify({"status": "ok"})


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Called when the browser tab closes."""
    _do_shutdown()
    return jsonify({"status": "shutting_down"})


def _do_shutdown():
    """Terminate the process."""
    os._exit(0)


def _watchdog():
    """Background thread: exits if no heartbeat received within timeout."""
    global _last_heartbeat
    while True:
        time.sleep(3)
        if time.time() - _last_heartbeat > _HEARTBEAT_TIMEOUT:
            _do_shutdown()


def start_server(open_browser=False, headless=False):
    """Start Flask with optional browser launch and watchdog."""
    global _last_heartbeat
    _last_heartbeat = time.time()

    if headless:
        # Start watchdog thread for auto-shutdown
        t = threading.Thread(target=_watchdog, daemon=True)
        t.start()

    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    app.run(debug=False, port=5000, use_reloader=False)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
