import tkinter as tk
from tkinter import messagebox
import threading
import base64
import sys

try:
    import msal
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "msal", "requests", "--quiet"])
    import msal
    import requests

# ═══════════════════════════════════════════════════════════════════════════
#  ENCODED CREDENTIALS  — run encode_creds.py once, paste output here,
#  then delete encode_creds.py before building the .exe
# ═══════════════════════════════════════════════════════════════════════════
_K = b"WinmarkSC2025"

def _d(s: str) -> str:
    raw = base64.b64decode(s.encode())
    return "".join(chr(b ^ _K[i % len(_K)]) for i, b in enumerate(raw))

_TENANT_ID     = "ZQpZW1ZBWDZuBggBVnpdCl5TX1JnJwMdAgM2XgoIBEUJNXYG"
_CLIENT_ID     = "ZwtfC1ZCCmRuBlJRA3pdX1xVX1IwdAAdUFZhCAheVUJeYXZW"
_CLIENT_SECRET = "IRMDVTAMOWEsfGp8AzE9XBkmNhM4FXtECwYUHjFDFQc/HG5EVVENMg=="
# ═══════════════════════════════════════════════════════════════════════════

MAILBOX   = "supportcenter@winmarkcorporation.com"
RULE_NAME = "Automate making all Cases (Nana test rule)"
SCOPE     = ["https://graph.microsoft.com/.default"]
GRAPH     = "https://graph.microsoft.com/v1.0"


def _get_token() -> str:
    tenant = _d(_TENANT_ID)
    client = msal.ConfidentialClientApplication(
        _d(_CLIENT_ID),
        authority=f"https://login.microsoftonline.com/{tenant}",
        client_credential=_d(_CLIENT_SECRET),
    )
    result = client.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Authentication failed — check app credentials."))
    return result["access_token"]


def _get_rules(token: str) -> list:
    r = requests.get(
        f"{GRAPH}/users/{MAILBOX}/mailFolders/inbox/messageRules",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("value", [])


def _set_rule(token: str, rule_id: str, enabled: bool) -> None:
    r = requests.patch(
        f"{GRAPH}/users/{MAILBOX}/mailFolders/inbox/messageRules/{rule_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"isEnabled": enabled},
        timeout=30,
    )
    r.raise_for_status()


class App(tk.Tk):
    BG   = "#1e1e2e"
    CARD = "#2a2a3d"
    FG   = "#e0e0f0"
    DIM  = "#8888aa"
    GRN  = "#3fb950"
    RED  = "#f85149"
    YLW  = "#e3b341"

    def __init__(self):
        super().__init__()
        self.title("Inbox Rule Toggle")
        self.geometry("460x300")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self._rule_id: str | None = None
        self._enabled: bool | None = None
        self._build_ui()
        self.after(150, self._refresh)

    def _build_ui(self):
        # Header
        tk.Label(self, text="Support Center  ·  Inbox Rule Manager",
                 font=("Segoe UI", 13, "bold"), bg=self.BG, fg=self.FG).pack(pady=(20, 2))
        tk.Label(self, text=MAILBOX, font=("Segoe UI", 9), bg=self.BG, fg=self.DIM).pack()
        tk.Label(self, text=f'"{RULE_NAME}"',
                 font=("Segoe UI", 9, "italic"), bg=self.BG, fg=self.DIM,
                 wraplength=420).pack(pady=(2, 18))

        # Status row
        row = tk.Frame(self, bg=self.BG)
        row.pack()
        tk.Label(row, text="Rule Status:", font=("Segoe UI", 12, "bold"),
                 bg=self.BG, fg=self.FG).grid(row=0, column=0, padx=(0, 10))
        self.lbl_status = tk.Label(row, text="Connecting…",
                                   font=("Segoe UI", 12, "bold"), bg=self.BG, fg=self.YLW)
        self.lbl_status.grid(row=0, column=1)

        # Buttons
        btns = tk.Frame(self, bg=self.BG)
        btns.pack(pady=20)

        self.btn_on = tk.Button(
            btns, text="  Turn ON  ", font=("Segoe UI", 10, "bold"),
            bg="#1f5c2e", fg="white", activebackground="#2a7a3e",
            relief="flat", bd=0, cursor="hand2", padx=4, pady=8,
            command=lambda: self._toggle(True))
        self.btn_on.grid(row=0, column=0, padx=8)

        self.btn_off = tk.Button(
            btns, text="  Turn OFF  ", font=("Segoe UI", 10, "bold"),
            bg="#6b1a1a", fg="white", activebackground="#8e2424",
            relief="flat", bd=0, cursor="hand2", padx=4, pady=8,
            command=lambda: self._toggle(False))
        self.btn_off.grid(row=0, column=1, padx=8)

        self.btn_ref = tk.Button(
            btns, text="  Refresh  ", font=("Segoe UI", 10),
            bg="#333355", fg="white", activebackground="#444477",
            relief="flat", bd=0, cursor="hand2", padx=4, pady=8,
            command=self._refresh)
        self.btn_ref.grid(row=0, column=2, padx=8)

        self.lbl_msg = tk.Label(self, text="", font=("Segoe UI", 9),
                                bg=self.BG, fg=self.DIM, wraplength=420)
        self.lbl_msg.pack()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _busy(self, msg="Working…"):
        self.lbl_msg.config(text=msg, fg=self.YLW)
        for b in (self.btn_on, self.btn_off, self.btn_ref):
            b.config(state="disabled")

    def _ready(self, msg=""):
        self.lbl_msg.config(text=msg, fg=self.DIM)
        self.btn_ref.config(state="normal")
        if self._enabled is None:
            return
        self.btn_on.config(state="disabled" if self._enabled else "normal")
        self.btn_off.config(state="normal" if self._enabled else "disabled")

    def _show_status(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self.lbl_status.config(text="ENABLED", fg=self.GRN)
        else:
            self.lbl_status.config(text="DISABLED", fg=self.RED)

    # ── network actions (run on background thread) ────────────────────────────

    def _refresh(self):
        self._busy("Connecting to Exchange…")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try:
            token = _get_token()
            rules = _get_rules(token)
            rule = next(
                (r for r in rules
                 if r.get("displayName", "").strip().lower() == RULE_NAME.strip().lower()),
                None,
            )
            if rule is None:
                self.after(0, lambda: self._err(f'Rule not found:\n"{RULE_NAME}"'))
                return
            self._rule_id = rule["id"]
            enabled = rule.get("isEnabled", False)
            self.after(0, lambda: (self._show_status(enabled), self._ready("Ready.")))
        except Exception as exc:
            self.after(0, lambda: self._err(str(exc)))

    def _toggle(self, enable: bool):
        self._busy("Updating rule…")
        threading.Thread(target=self._do_toggle, args=(enable,), daemon=True).start()

    def _do_toggle(self, enable: bool):
        try:
            token = _get_token()
            _set_rule(token, self._rule_id, enable)
            word = "enabled" if enable else "disabled"
            self.after(0, lambda: (self._show_status(enable),
                                   self._ready(f"Rule successfully {word}.")))
        except Exception as exc:
            self.after(0, lambda: self._err(str(exc)))

    def _err(self, msg: str):
        self._ready("")
        self.lbl_status.config(text="Error", fg=self.YLW)
        messagebox.showerror("Error", msg, parent=self)


if __name__ == "__main__":
    app = App()
    app.mainloop()
