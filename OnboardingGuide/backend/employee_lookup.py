"""
Employee lookup module — fetches data from the Winmark address book API
and provides search functions for the chatbot.
"""
import urllib.request
import json

ADDRESSBOOK_API = "https://addressbook.winmarkcorporation.com/api/employees"
_employees = []


def fetch_employees():
    """Fetch employee list from the address book API. Cache in memory."""
    global _employees
    if _employees:
        return _employees
    try:
        req = urllib.request.Request(ADDRESSBOOK_API, headers={"User-Agent": "WinmarkOnboarding/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            _employees = data.get("employees", [])
    except Exception:
        _employees = []
    return _employees


def search_employees(query: str) -> list:
    """Search employees by name, department, title, or extension."""
    employees = fetch_employees()
    if not employees:
        return []

    query_lower = query.lower().strip()
    results = []

    for emp in employees:
        score = 0
        full_name = f"{emp.get('firstName', '')} {emp.get('lastName', '')}".lower()
        first = emp.get("firstName", "").lower()
        last = emp.get("lastName", "").lower()
        title = emp.get("title", "").lower()
        dept = emp.get("department", "").lower()
        ext = emp.get("phoneExtension", "")

        # Exact full name match
        if query_lower == full_name:
            score += 10
        # Last name match
        elif query_lower == last:
            score += 8
        # First name match
        elif query_lower == first:
            score += 7
        # Partial name match
        elif query_lower in full_name:
            score += 5
        # Department match
        if query_lower in dept or dept in query_lower:
            score += 4
        # Title match
        if query_lower in title:
            score += 3
        # Extension match
        if query_lower == ext:
            score += 10

        if score > 0:
            results.append((score, emp))

    results.sort(key=lambda x: (-x[0], x[1].get("lastName", "")))
    return [emp for _, emp in results[:10]]


def format_employee(emp: dict) -> str:
    """Format a single employee into a readable string."""
    name = f"{emp.get('firstName', '')} {emp.get('lastName', '')}"
    title = emp.get("title", "N/A")
    dept = emp.get("department", "N/A")
    ext = emp.get("phoneExtension", "N/A")
    email = emp.get("email", "N/A")
    lead = " ⭐ Department Lead" if emp.get("isDepartmentLead") else ""
    return f"**{name}**{lead}\n• Title: {title}\n• Department: {dept}\n• Extension: {ext}\n• Email: {email}"


def format_employee_list(employees: list) -> str:
    """Format a list of employees into a chatbot response."""
    if not employees:
        return None
    if len(employees) == 1:
        return f"Here's what I found:\n\n{format_employee(employees[0])}"
    parts = [f"I found {len(employees)} matches:\n"]
    for emp in employees:
        name = f"{emp.get('firstName', '')} {emp.get('lastName', '')}"
        title = emp.get("title", "N/A")
        dept = emp.get("department", "N/A")
        ext = emp.get("phoneExtension", "N/A")
        lead = " ⭐" if emp.get("isDepartmentLead") else ""
        parts.append(f"• **{name}**{lead} — {title}, {dept} (ext. {ext})")
    return "\n".join(parts)


def detect_employee_query(message: str) -> str | None:
    """
    Detect if a chat message is asking about an employee or department.
    Returns the search term, or None if not an employee query.
    """
    msg = message.lower().strip()

    # Direct triggers
    triggers = [
        "who is ", "who's ", "find ", "look up ", "lookup ",
        "search for ", "contact for ", "contact info for ",
        "what is the extension for ", "what's the extension for ",
        "extension for ", "ext for ", "ext. for ",
        "what department is ", "what dept is ",
        "who works in ", "who is in ", "people in ",
        "employees in ", "staff in ", "team in ",
    ]

    for trigger in triggers:
        if msg.startswith(trigger):
            return msg[len(trigger):].strip().rstrip("?").strip()

    # "department" keyword in query
    dept_keywords = [
        "technology", "finance", "marketing", "legal", "training",
        "human resources", "hr", "executive", "franchise development",
        "operations", "shared services", "plato", "once upon a child",
        "play it again", "music go round", "style encore",
    ]
    for dk in dept_keywords:
        if dk in msg and any(w in msg for w in ["who", "people", "team", "staff", "employees", "department", "dept"]):
            return dk

    return None
