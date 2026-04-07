"""
Winmark Onboarding Guide — Launcher
Starts the Flask server (hidden console) and opens the browser.
When the browser tab is closed, the server shuts down automatically.
"""
import sys
import os
import time
import threading
import webbrowser
import socket

# --------------- path setup ---------------
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

# --------------- imports from backend ---------------
from flask import Flask, request, jsonify, render_template  # noqa: E402
from flask_cors import CORS  # noqa: E402
from faq_data import FAQ_ENTRIES  # noqa: E402
from employee_lookup import detect_employee_query, search_employees, format_employee_list  # noqa: E402

# --------------- build app ---------------
TEMPLATE_DIR = os.path.join(BACKEND_DIR, 'templates')
STATIC_DIR = os.path.join(BACKEND_DIR, 'static')
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
CORS(app)

_last_heartbeat = time.time()
_HEARTBEAT_TIMEOUT = 10


def find_best_answer(user_message: str) -> dict:
    message_lower = user_message.lower().strip()
    if not message_lower:
        return {"question": "Empty", "answer": "Try asking about company info, IT setup, HR, or facilities!", "confidence": 0}
    best_match = None
    best_score = 0
    for entry in FAQ_ENTRIES:
        score = sum(len(kw.lower().split()) for kw in entry["keywords"] if kw.lower() in message_lower)
        if score > best_score:
            best_score = score
            best_match = entry
    if best_match and best_score > 0:
        return {"question": best_match["question"], "answer": best_match["answer"], "confidence": min(best_score / 3.0, 1.0)}
    return {
        "question": user_message,
        "answer": (
            "I'm not sure about that one! I can help with:\n"
            "• **Company info** – Winmark, our brands, mission\n"
            "• **IT setup** – Email, software, passwords\n"
            "• **Benefits & HR** – PTO, insurance, payroll\n"
            "• **Facilities** – Parking, break room, office hours\n"
            "• **Address Book** – Coworker contacts\n\n"
            "Try rephrasing your question!"
        ),
        "confidence": 0,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
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
            "reply": f'I couldn\'t find anyone matching "{search_term}". Try searching by first name, last name, or department.',
            "matched_question": user_message,
        })

    result = find_best_answer(user_message)
    return jsonify({"reply": result["answer"], "matched_question": result["question"]})


@app.route("/api/faq", methods=["GET"])
def get_faq():
    return jsonify({"questions": [
        "How do I set up my email?", "What is the PTO policy?",
        "What benefits does Winmark offer?", "Where do I park?",
        "What is the dress code?", "How do I find a coworker's contact info?",
    ]})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return jsonify({"status": "ok"})


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    os._exit(0)


def _watchdog():
    global _last_heartbeat
    while True:
        time.sleep(3)
        if time.time() - _last_heartbeat > _HEARTBEAT_TIMEOUT:
            os._exit(0)


def find_free_port():
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


if __name__ == '__main__':
    port = find_free_port()
    _last_heartbeat = time.time()
    threading.Thread(target=_watchdog, daemon=True).start()
    threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(debug=False, port=port, use_reloader=False)
