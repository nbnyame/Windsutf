"""
DRS Version Audit - GUI
=======================
Tkinter-based GUI for browsing stores on DRS 8.9.6 or lower.
Fetches data from Dynamics 365 CRM in a background thread so the UI stays responsive.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv

# ── Path setup so we can import from parent dir ──────────────────────────────
_HERE       = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_HERE)
sys.path.insert(0, _PARENT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PARENT_DIR, ".env"))

from drs_version_audit import (
    build_drs_option_map,
    run_audit,
    discover_timezone_field,
    _PARENT_DIR as _AUDIT_PARENT,
)

# ── Constants ─────────────────────────────────────────────────────────────────
CRM_DRS_VERSION_FIELD = os.getenv("CRM_DRS_VERSION_FIELD", "win_drsversion1")
CRM_TIMEZONE_FIELD    = os.getenv("CRM_TIMEZONE_FIELD", "")

PAGE_SIZE = 50

# Timezone badge colours (bg, fg)
TZ_COLORS = {
    "PT":      ("#1d6fa4", "white"),
    "MT":      ("#2e7d32", "white"),
    "CT":      ("#e65100", "white"),
    "ET":      ("#6a1b9a", "white"),
    "AT":      ("#ad1457", "white"),
    "Unknown": ("#616161", "white"),
}

# ── Main Application ──────────────────────────────────────────────────────────

class DrsAuditApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("DRS Version Audit")
        self.geometry("1050x680")
        self.minsize(800, 500)
        self.configure(bg="#f0f0f0")

        self._all_results   = []   # full unfiltered result list
        self._filtered      = []   # after search/TZ filter
        self._page          = 0
        self._loading       = False

        self._build_ui()
        self.after(100, self._start_fetch)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header bar ──
        header = tk.Frame(self, bg="#1565c0", pady=10)
        header.pack(fill="x")
        tk.Label(
            header, text="DRS Version Audit",
            font=("Segoe UI", 16, "bold"), bg="#1565c0", fg="white"
        ).pack(side="left", padx=16)
        self._status_var = tk.StringVar(value="Connecting to CRM...")
        tk.Label(
            header, textvariable=self._status_var,
            font=("Segoe UI", 10), bg="#1565c0", fg="#bbdefb"
        ).pack(side="left", padx=8)

        self._refresh_btn = tk.Button(
            header, text="Refresh", font=("Segoe UI", 9),
            bg="#0d47a1", fg="white", relief="flat",
            padx=10, cursor="hand2", command=self._start_fetch,
        )
        self._refresh_btn.pack(side="right", padx=12)

        self._export_btn = tk.Button(
            header, text="Export CSV", font=("Segoe UI", 9),
            bg="#0d47a1", fg="white", relief="flat",
            padx=10, cursor="hand2", command=self._export_csv,
        )
        self._export_btn.pack(side="right", padx=4)

        # ── Filter bar ──
        filter_bar = tk.Frame(self, bg="#e3f2fd", pady=6)
        filter_bar.pack(fill="x")

        tk.Label(filter_bar, text="Filter by TZ:", bg="#e3f2fd",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 4))

        self._tz_var = tk.StringVar(value="All")
        tz_options = ["All", "PT", "MT", "CT", "ET", "AT", "Unknown"]
        self._tz_menu = ttk.Combobox(
            filter_bar, textvariable=self._tz_var, values=tz_options,
            state="readonly", width=10, font=("Segoe UI", 9),
        )
        self._tz_menu.pack(side="left", padx=4)
        self._tz_menu.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        tk.Label(filter_bar, text="  Search store / name:",
                 bg="#e3f2fd", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(16, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        search_entry = tk.Entry(
            filter_bar, textvariable=self._search_var,
            font=("Segoe UI", 9), width=28,
        )
        search_entry.pack(side="left", padx=4)

        tk.Button(
            filter_bar, text="Clear", font=("Segoe UI", 8),
            relief="flat", bg="#90caf9", cursor="hand2",
            command=self._clear_filter,
        ).pack(side="left", padx=6)

        self._count_var = tk.StringVar(value="")
        tk.Label(filter_bar, textvariable=self._count_var,
                 bg="#e3f2fd", font=("Segoe UI", 9, "italic"),
                 fg="#555").pack(side="right", padx=12)

        # ── Loading bar ──
        self._progress = ttk.Progressbar(self, mode="indeterminate")
        self._progress.pack(fill="x", padx=0)

        # ── Table ──
        table_frame = tk.Frame(self, bg="#f0f0f0")
        table_frame.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        cols = ("tz", "store", "drs_version", "server_model", "store_name")
        self._tree = ttk.Treeview(
            table_frame, columns=cols, show="headings",
            selectmode="browse",
        )

        col_cfg = [
            ("tz",           "TZ",           70,  "center"),
            ("store",        "Store #",      90,  "center"),
            ("drs_version",  "DRS Version",  200, "w"),
            ("server_model", "Server Model", 200, "w"),
            ("store_name",   "Store Name",   380, "w"),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._sort_by(c))
            self._tree.column(col_id, width=width, anchor=anchor, stretch=(col_id == "store_name"))

        # Alternating row colours + TZ tag colours
        self._tree.tag_configure("odd",  background="#ffffff")
        self._tree.tag_configure("even", background="#f5f9ff")
        for tz, (bg, fg) in TZ_COLORS.items():
            self._tree.tag_configure(f"tz_{tz}", background=bg, foreground=fg)

        vsb = ttk.Scrollbar(table_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Row double-click → detail popup
        self._tree.bind("<Double-1>", self._show_detail)

        # ── Pagination bar ──
        pager = tk.Frame(self, bg="#f0f0f0", pady=6)
        pager.pack(fill="x")

        self._prev_btn = tk.Button(
            pager, text="<< Prev", font=("Segoe UI", 9),
            relief="flat", bg="#1565c0", fg="white",
            padx=14, cursor="hand2", command=self._prev_page,
        )
        self._prev_btn.pack(side="left", padx=12)

        self._page_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(pager, textvariable=self._page_var,
                 font=("Segoe UI", 9), bg="#f0f0f0").pack(side="left", padx=8)

        self._next_btn = tk.Button(
            pager, text="Next >>", font=("Segoe UI", 9),
            relief="flat", bg="#1565c0", fg="white",
            padx=14, cursor="hand2", command=self._next_page,
        )
        self._next_btn.pack(side="left", padx=4)

        # Jump-to-page
        tk.Label(pager, text="  Go to page:", font=("Segoe UI", 9),
                 bg="#f0f0f0").pack(side="left", padx=(20, 4))
        self._jump_var = tk.StringVar()
        jump_entry = tk.Entry(pager, textvariable=self._jump_var,
                              width=5, font=("Segoe UI", 9))
        jump_entry.pack(side="left")
        jump_entry.bind("<Return>", self._jump_page)
        tk.Button(
            pager, text="Go", font=("Segoe UI", 9),
            relief="flat", bg="#546e7a", fg="white",
            padx=8, cursor="hand2", command=self._jump_page,
        ).pack(side="left", padx=4)

        # Max version selector
        tk.Label(pager, text="  Max DRS version:",
                 font=("Segoe UI", 9), bg="#f0f0f0").pack(side="right", padx=(0, 4))
        self._max_ver_var = tk.StringVar(value="8.9.6")
        max_ver_entry = tk.Entry(pager, textvariable=self._max_ver_var,
                                 width=8, font=("Segoe UI", 9))
        max_ver_entry.pack(side="right", padx=(0, 12))
        max_ver_entry.bind("<Return>", lambda e: self._start_fetch())

    # ── Data Fetching (background thread) ────────────────────────────────────

    def _start_fetch(self):
        if self._loading:
            return
        self._loading = True
        self._refresh_btn.config(state="disabled")
        self._export_btn.config(state="disabled")
        self._status_var.set("Connecting to CRM...")
        self._progress.start(12)
        self._all_results = []
        self._filtered    = []
        self._render_page()
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            from crm_client import Dynamics365Client

            self._set_status("Authenticating...")
            crm = Dynamics365Client()
            crm.authenticate()

            self._set_status("Loading DRS version options...")
            _, code_to_label = build_drs_option_map(crm, CRM_DRS_VERSION_FIELD)

            tz_field = CRM_TIMEZONE_FIELD or None
            if not tz_field:
                self._set_status("Detecting timezone field...")
                sample = crm._request("GET", "accounts", params={
                    "$filter": "statecode eq 0",
                    "$select": "accountid",
                    "$top": 1,
                }).json().get("value", [])
                if sample:
                    tz_field = discover_timezone_field(crm, sample[0]["accountid"])

            max_ver = self._max_ver_var.get().strip() or "8.9.6"
            self._set_status(f"Fetching stores (DRS <= {max_ver})...")
            results = run_audit(crm, CRM_DRS_VERSION_FIELD, tz_field, max_ver, code_to_label)

            self._all_results = results
            self._set_status(f"Loaded {len(results)} stores on DRS {max_ver} or lower.")
            self.after(0, lambda: self._on_fetch_complete())

        except Exception as e:
            self.after(0, lambda m=str(e): self._on_fetch_error(m))

    def _on_fetch_complete(self):
        self._loading = False
        self._progress.stop()
        self._progress.config(value=0)
        self._refresh_btn.config(state="normal")
        self._export_btn.config(state="normal")
        self._apply_filter()

    def _on_fetch_error(self, msg):
        self._loading = False
        self._progress.stop()
        self._refresh_btn.config(state="normal")
        self._status_var.set("Error — see details")
        messagebox.showerror("CRM Error", f"Failed to load data:\n\n{msg}")

    def _set_status(self, msg):
        self.after(0, lambda: self._status_var.set(msg))

    # ── Filter & Search ───────────────────────────────────────────────────────

    def _apply_filter(self):
        tz   = self._tz_var.get()
        term = self._search_var.get().strip().lower()

        filtered = self._all_results
        if tz != "All":
            filtered = [r for r in filtered if r["tz_bucket"] == tz]
        if term:
            filtered = [
                r for r in filtered
                if term in r["store_number"].lower() or term in r["name"].lower()
                or term in r["drs_label"].lower()
            ]

        self._filtered = filtered
        self._page     = 0
        self._count_var.set(f"{len(filtered)} store(s) shown")
        self._render_page()

    def _clear_filter(self):
        self._tz_var.set("All")
        self._search_var.set("")
        self._apply_filter()

    # ── Pagination ────────────────────────────────────────────────────────────

    def _total_pages(self):
        return max(1, (len(self._filtered) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _render_page(self):
        self._tree.delete(*self._tree.get_children())
        total = self._total_pages()
        self._page_var.set(f"Page {self._page + 1} of {total}")
        self._prev_btn.config(state="normal" if self._page > 0 else "disabled")
        self._next_btn.config(state="normal" if self._page < total - 1 else "disabled")

        start = self._page * PAGE_SIZE
        rows  = self._filtered[start:start + PAGE_SIZE]

        for i, r in enumerate(rows):
            tag_row = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(r["tz_bucket"], r["store_number"], r["drs_label"], r.get("server_model", ""), r["name"]),
                tags=(tag_row,),
            )

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self):
        if self._page < self._total_pages() - 1:
            self._page += 1
            self._render_page()

    def _jump_page(self, event=None):
        try:
            target = int(self._jump_var.get()) - 1
            if 0 <= target < self._total_pages():
                self._page = target
                self._render_page()
        except ValueError:
            pass
        finally:
            self._jump_var.set("")

    def _sort_by(self, col):
        """Toggle ascending/descending sort on a column."""
        key_map = {
            "tz":           lambda r: (r["tz_bucket"], r["store_number"]),
            "store":        lambda r: r["store_number"],
            "drs_version":  lambda r: r["drs_version"] or (0,),
            "server_model": lambda r: r.get("server_model", "").lower(),
            "store_name":   lambda r: r["name"].lower(),
        }
        if not hasattr(self, "_sort_col"):
            self._sort_col = None
            self._sort_asc = True

        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        self._filtered.sort(key=key_map[col], reverse=not self._sort_asc)
        self._page = 0
        self._render_page()

    # ── Row Detail Popup ──────────────────────────────────────────────────────

    def _show_detail(self, event):
        sel = self._tree.focus()
        if not sel:
            return
        vals = self._tree.item(sel, "values")
        if not vals:
            return
        tz, store, drs, server, name = vals

        popup = tk.Toplevel(self)
        popup.title(f"Store {store} Details")
        popup.geometry("420x250")
        popup.resizable(False, False)
        popup.configure(bg="#f0f0f0")
        popup.grab_set()

        frame = tk.Frame(popup, bg="#1565c0")
        frame.pack(fill="x")
        tk.Label(frame, text=f"Store {store}", font=("Segoe UI", 13, "bold"),
                 bg="#1565c0", fg="white", pady=8).pack(padx=12)

        body = tk.Frame(popup, bg="#f0f0f0", padx=20, pady=12)
        body.pack(fill="both", expand=True)

        def row(label, value, r):
            tk.Label(body, text=label, font=("Segoe UI", 9, "bold"),
                     bg="#f0f0f0", anchor="w").grid(row=r, column=0, sticky="w", pady=3)
            tk.Label(body, text=value, font=("Segoe UI", 9),
                     bg="#f0f0f0", anchor="w").grid(row=r, column=1, sticky="w", padx=12)

        row("Store Name:",   name, 0)
        row("Store Number:", store, 1)
        row("DRS Version:",  drs, 2)
        row("Server Model:", server, 3)
        row("Time Zone:",    tz, 4)

        tk.Button(popup, text="Close", command=popup.destroy,
                  font=("Segoe UI", 9), relief="flat",
                  bg="#1565c0", fg="white", padx=16, cursor="hand2",
                  ).pack(pady=(0, 14))

    # ── CSV Export ────────────────────────────────────────────────────────────

    def _export_csv(self):
        if not self._filtered:
            messagebox.showinfo("Export", "No data to export.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"drs_audit_{ts}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name,
            title="Save DRS Audit CSV",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timezone", "store_number", "store_name", "drs_version", "server_model", "account_id"])
            writer.writeheader()
            for r in self._filtered:
                writer.writerow({
                    "timezone":     r["tz_bucket"],
                    "store_number": r["store_number"],
                    "store_name":   r["name"],
                    "drs_version":  r["drs_label"],
                    "server_model": r.get("server_model", ""),
                    "account_id":   r["account_id"],
                })
        messagebox.showinfo("Export Complete", f"Saved to:\n{path}")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DrsAuditApp()
    app.mainloop()
