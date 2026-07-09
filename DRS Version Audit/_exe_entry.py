"""
Standalone entry point for the DRS Audit .exe build.
Credentials are embedded at build time — no .env file required at runtime.
"""

import os
import sys

# ── Embed credentials so no .env is needed at runtime ────────────────────────
os.environ.setdefault("CRM_URL",              "https://winmarkcrm.winmarkcorporation.com:444")
os.environ.setdefault("CRM_DOMAIN",           "winmarkcorp.net")
os.environ.setdefault("CRM_USERNAME",         "nnyamekye")
os.environ.setdefault("CRM_PASSWORD",         "Jungle23&")
os.environ.setdefault("CRM_DRS_VERSION_FIELD","win_drsversion1")
os.environ.setdefault("CRM_TIMEZONE_FIELD",   "win_timezone")

# ── When frozen by PyInstaller, sys._MEIPASS is the temp extraction folder.
# Add it to sys.path so all bundled modules are importable. ──────────────────
if getattr(sys, "frozen", False):
    _base = sys._MEIPASS
else:
    _base = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _base)

# ── Launch the GUI ────────────────────────────────────────────────────────────
from drs_audit_gui import DrsAuditApp

if __name__ == "__main__":
    app = DrsAuditApp()
    app.mainloop()
