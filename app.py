#!/usr/bin/env python3
"""
Tkinter GUI for the finance panel.
- Multi-account switching/creation.
- Add transaction via form.
- Import CSV/JSON (array of objects) with columns: date, amount, type, category, description, method.
- Export current account to CSV.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

EXPENSE_CATEGORIES = ["Meals", "Transport", "Subscriptions", "Groceries", "Fun", "Utilities", "Other"]
INCOME_CATEGORIES = ["Salary", "Allowance", "Bonus", "Part-time", "Other"]


def categories_for_type(tx_type: str) -> List[str]:
    return INCOME_CATEGORIES if tx_type == "income" else EXPENSE_CATEGORIES

DEFAULT_ACCOUNTS: Dict[str, List[Dict[str, object]]] = {
    "Case A": [],
    "Case B": [],
    "Case C": [],
    "Case D": [],
}

Transaction = Dict[str, object]
ImportStats = Dict[str, int]

MISSING_CATEGORY_LABEL = "Missing Category [Review]"
MISSING_FLAGS_KEY = "missing_flags"

HEADER_ALIASES: Dict[str, List[str]] = {
    "date": ["date", "transaction_date"],
    "amount": ["amount", "amount_in_hkd", "amount_hkd", "amountinhkd", "value"],
    "type": ["type", "transaction_type"],
    "category": ["category", "cat"],
    "description": ["description", "memo", "details", "note"],
    "method": ["method", "payment", "payment_method"],
}


def format_currency(amount: float) -> str:
    return f"${amount:.2f}"


def month_key(date_str: str) -> str:
    try:
        d = parse_date_safe(date_str)
        return d.strftime("%Y-%m")
    except Exception:
        return ""


def parse_date_safe(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def normalize_header(value: str) -> str:
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def parse_amount_safe(value: str) -> float | None:
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        return abs(float(cleaned))
    except Exception:
        return None


def infer_type(raw_type: str, category: str, amount: float) -> str:
    tx_type = raw_type.strip().lower()
    if tx_type in ("expense", "income"):
        return tx_type
    if not category.strip() or category == MISSING_CATEGORY_LABEL:
        return "unknown"
    income_cats = {name.lower() for name in INCOME_CATEGORIES}
    if category.strip().lower() in income_cats:
        return "income"
    return "expense"


def init_import_stats() -> ImportStats:
    return {
        "imported": 0,
        "skipped": 0,
        "flagged": 0,
        "missing_category_records": 0,
        "unknown_type_records": 0,
        "filled_date": 0,
        "filled_amount": 0,
        "filled_category": 0,
        "filled_description": 0,
        "filled_method": 0,
        "filled_type": 0,
    }


def repair_transaction(
    raw_date: str,
    raw_amount: str,
    raw_type: str,
    raw_category: str,
    raw_desc: str,
    raw_method: str,
    last_valid_date: str,
    stats: ImportStats,
) -> Transaction | None:
    date_str = raw_date.strip()
    missing_flags: List[str] = []
    if not date_str:
        if not last_valid_date:
            stats["skipped"] += 1
            return None
        date_str = last_valid_date
        stats["filled_date"] += 1
        missing_flags.append("missing date")
    try:
        date_obj = parse_date_safe(date_str)
    except Exception:
        if not last_valid_date:
            stats["skipped"] += 1
            return None
        try:
            date_obj = parse_date_safe(last_valid_date)
            stats["filled_date"] += 1
            missing_flags.append("invalid date")
        except Exception:
            stats["skipped"] += 1
            return None

    amount = parse_amount_safe(raw_amount)
    if amount is None:
        amount = 0.0
        stats["filled_amount"] += 1
        missing_flags.append("missing amount")

    category = raw_category.strip() or MISSING_CATEGORY_LABEL
    if not raw_category.strip():
        stats["filled_category"] += 1
        stats["missing_category_records"] += 1
        missing_flags.append("missing category")

    description = raw_desc.strip() or "Imported"
    if not raw_desc.strip():
        stats["filled_description"] += 1

    method = raw_method.strip() or "Imported"
    if not raw_method.strip():
        stats["filled_method"] += 1

    tx_type = infer_type(raw_type, category, amount)
    if raw_type.strip().lower() not in ("expense", "income"):
        stats["filled_type"] += 1
    if tx_type == "unknown":
        stats["unknown_type_records"] += 1
        missing_flags.append("unknown type")

    if missing_flags:
        stats["flagged"] += 1

    stats["imported"] += 1
    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "amount": amount,
        "type": tx_type,
        "category": category,
        "description": description,
        "method": method,
        MISSING_FLAGS_KEY: missing_flags,
    }


def days_in_month(d: date) -> int:
    next_month = d.replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).day


def load_csv(path: Path) -> Tuple[List[Transaction], ImportStats]:
    rows: List[Transaction] = []
    stats = init_import_stats()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header: List[str] = []
        normalized_header: List[str] = []
        last_valid_date = ""
        for idx, cols in enumerate(reader):
            if not cols or all(not c.strip() for c in cols):
                continue
            if idx == 0:
                header = [c.strip() for c in cols]
                normalized_header = [normalize_header(c) for c in cols]
                # Decide whether this is a header row by checking typical column names
                if any(h in normalized_header for names in HEADER_ALIASES.values() for h in names):
                    continue  # treat as header
            # Map columns by position with header hints
            def pick(col_names: List[str], default_index: int | None = None) -> str:
                for name in col_names:
                    if name in normalized_header:
                        index = normalized_header.index(name)
                        if index < len(cols):
                            return cols[index].strip()
                if default_index is not None and default_index < len(cols):
                    return cols[default_index].strip()
                return ""

            has_id_prefix = bool(normalized_header) and normalized_header[0] in {"transaction_id", "id"}
            raw_date = pick(HEADER_ALIASES["date"], 1 if has_id_prefix else 0)
            raw_amount = pick(HEADER_ALIASES["amount"], 2 if has_id_prefix else 1)
            raw_type = pick(HEADER_ALIASES["type"], None)
            raw_category = pick(HEADER_ALIASES["category"], 3 if has_id_prefix else 2)
            raw_desc = pick(HEADER_ALIASES["description"], 4 if has_id_prefix else 3)
            raw_method = pick(HEADER_ALIASES["method"], 5 if has_id_prefix else None)

            tx = repair_transaction(
                raw_date,
                raw_amount,
                raw_type,
                raw_category,
                raw_desc,
                raw_method,
                last_valid_date,
                stats,
            )
            if tx is None:
                print(f"[skip] invalid row {idx + 1}: {cols}")
                continue
            last_valid_date = str(tx["date"])
            rows.append(tx)
    return rows, stats


def load_json(path: Path) -> Tuple[List[Transaction], ImportStats]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        messagebox.showerror("Import failed", "JSON root must be an array")
        return [], init_import_stats()
    rows: List[Transaction] = []
    stats = init_import_stats()
    last_valid_date = ""
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            print(f"[skip] invalid item #{idx + 1}: {item}")
            stats["skipped"] += 1
            continue
        tx = repair_transaction(
            str(item.get("date", "")),
            str(item.get("amount", "")),
            str(item.get("type", "")),
            str(item.get("category", "")),
            str(item.get("description", "")),
            str(item.get("method", "")),
            last_valid_date,
            stats,
        )
        if tx is None:
            print(f"[skip] invalid item #{idx + 1}: {item}")
            continue
        last_valid_date = str(tx["date"])
        rows.append(tx)
    return rows, stats


def summarize_import(stats: ImportStats) -> str:
    repaired = sum(stats[key] for key in stats if key.startswith("filled_"))
    parts = [f"Imported {stats['imported']} records"]
    if stats["flagged"]:
        parts.append(f"flagged {stats['flagged']} incomplete transactions")
    if stats["missing_category_records"]:
        parts.append(f"{stats['missing_category_records']} missing category")
    if stats["unknown_type_records"]:
        parts.append(f"{stats['unknown_type_records']} unknown type")
    if repaired:
        parts.append(f"repaired {repaired} missing fields")
    if stats["skipped"]:
        parts.append(f"skipped {stats['skipped']} invalid rows")
    return " | ".join(parts)


def export_csv(path: Path, txs: List[Transaction]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "amount", "type", "category", "description", "method"])
        for t in txs:
            writer.writerow([
                t.get("date", ""),
                t.get("amount", ""),
                t.get("type", ""),
                t.get("category", ""),
                t.get("description", ""),
                t.get("method", ""),
            ])


def summarize(txs: List[Transaction], month_selector: str = "All Months") -> Dict[str, float]:
    spent = sum(t["amount"] for t in txs if t.get("type") == "expense")
    income = sum(t["amount"] for t in txs if t.get("type") == "income")
    balance = income - spent
    today = date.today()

    # Month selection handling
    if month_selector != "All Months" and month_selector:
        try:
            ref_month = datetime.strptime(month_selector, "%Y-%m").date()
        except Exception:
            ref_month = today
        start_month = ref_month.replace(day=1)
        dim = days_in_month(start_month)
        # If not current month, treat as full month completed
        day = today.day if (today.year == start_month.year and today.month == start_month.month) else dim
    else:
        start_month = today.replace(day=1)
        dim = days_in_month(today)
        day = today.day

    week_ago = today - timedelta(days=7)
    spent_week = sum(
        t["amount"] for t in txs if t.get("type") == "expense" and parse_date_safe(str(t.get("date"))) >= week_ago
    )
    spent_subs = sum(t["amount"] for t in txs if str(t.get("category")) == "Subscriptions")

    spent_month = sum(
        t["amount"] for t in txs if t.get("type") == "expense" and parse_date_safe(str(t.get("date"))) >= start_month and parse_date_safe(str(t.get("date"))).month == start_month.month and parse_date_safe(str(t.get("date"))).year == start_month.year
    )
    daily_avg = spent_month / max(day, 1)
    projected = daily_avg * dim
    return {
        "spent": spent,
        "income": income,
        "balance": balance,
        "spent_week": spent_week,
        "spent_subs": spent_subs,
        "spent_month": spent_month,
        "projected": projected,
        "day": day,
        "dim": dim,
    }


def category_breakdown(txs: List[Transaction]) -> List[Tuple[str, float]]:
    agg: Dict[str, float] = {}
    for t in txs:
        if t.get("type") != "expense":
            continue
        cat = str(t.get("category", "Other"))
        agg[cat] = agg.get(cat, 0) + float(t.get("amount", 0))
    return sorted(agg.items(), key=lambda kv: kv[1], reverse=True)


class FinanceApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Everyday Finance · Python GUI")
        self.root.geometry("1040x680")
        self.root.configure(bg="#0f1629")

        self.accounts: Dict[str, List[Transaction]] = {k: [dict(t) for t in v] for k, v in DEFAULT_ACCOUNTS.items()}
        self.active_account: tk.StringVar = tk.StringVar(value="Case A")
        self.month_filter: tk.StringVar = tk.StringVar(value="All Months")
        self.trend_category: tk.StringVar = tk.StringVar(value="All Categories")

        self.summary_var = tk.StringVar()
        self.forecast_var = tk.StringVar()
        self.visible_tx_indices: List[int] = []

        self._setup_styles()
        self._build_ui()
        self.refresh()

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TFrame",
            background="#131c33",
        )
        style.configure(
            "TLabel",
            background="#131c33",
            foreground="#d9e5ff",
            font=("Helvetica Neue", 11),
        )
        style.configure(
            "Header.TLabel",
            font=("Helvetica Neue", 14, "bold"),
        )
        style.configure(
            "Accent.TButton",
            background="#3fe0a8",
            foreground="#0b1324",
            padding=6,
        )
        style.map("Accent.TButton", background=[("active", "#35c692")])
        style.configure("TButton", padding=6)
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground="#1a1a1a")
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#1b2740",
            bordercolor="#1b2740",
            background="#3fe0a8",
            lightcolor="#3fe0a8",
            darkcolor="#35c692",
        )

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Account:").pack(side=tk.LEFT)
        self.account_combo = ttk.Combobox(top, textvariable=self.active_account, values=list(self.accounts.keys()), width=18, state="readonly")
        self.account_combo.pack(side=tk.LEFT, padx=6)
        self.account_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        ttk.Button(top, text="New Account", command=self.create_account).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Import CSV/JSON", command=self.import_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Export CSV", command=self.export_file).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="Month:").pack(side=tk.LEFT, padx=(16, 4))
        self.month_combo = ttk.Combobox(top, textvariable=self.month_filter, values=["All Months"], width=12, state="readonly")
        self.month_combo.pack(side=tk.LEFT)
        self.month_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        # Summary area
        summary_frame = ttk.Frame(self.root, padding=10, borderwidth=1, relief=tk.GROOVE)
        summary_frame.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(summary_frame, textvariable=self.summary_var, anchor="w", justify=tk.LEFT, font=("Helvetica Neue", 12, "bold")).pack(fill=tk.X)
        ttk.Label(summary_frame, textvariable=self.forecast_var, anchor="w", justify=tk.LEFT, foreground="#9bb0d1").pack(fill=tk.X)

        # Analytics area (categories + insights)
        analytics = ttk.Frame(self.root, padding=10)
        analytics.pack(fill=tk.X, padx=8, pady=4)

        self.cat_frame = ttk.Frame(analytics, padding=10, borderwidth=1, relief=tk.GROOVE)
        self.cat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ttk.Label(self.cat_frame, text="Categories", style="Header.TLabel").pack(anchor="w")
        self.cat_body = ttk.Frame(self.cat_frame)
        self.cat_body.pack(fill=tk.BOTH, expand=True, pady=6)

        self.insight_frame = ttk.Frame(analytics, padding=10, borderwidth=1, relief=tk.GROOVE)
        self.insight_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        ttk.Label(self.insight_frame, text="Insights / Quick tips", style="Header.TLabel").pack(anchor="w")
        self.insight_body = ttk.Frame(self.insight_frame)
        self.insight_body.pack(fill=tk.BOTH, expand=True, pady=6)

        # Spending Trend chart (right panel)
        trend_frame = ttk.Frame(analytics, padding=10, borderwidth=1, relief=tk.GROOVE)
        trend_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        trend_header = ttk.Frame(trend_frame)
        trend_header.pack(fill=tk.X)
        ttk.Label(trend_header, text="Spending Trend", style="Header.TLabel").pack(side=tk.LEFT, anchor="w")
        self.trend_category_combo = ttk.Combobox(
            trend_header,
            textvariable=self.trend_category,
            values=["All Categories"],
            width=16,
            state="readonly",
        )
        self.trend_category_combo.pack(side=tk.RIGHT)
        self.trend_category_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.trend_canvas = tk.Canvas(trend_frame, bg="#0f1629", highlightthickness=0)
        self.trend_canvas.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.trend_canvas.bind("<Configure>", lambda e: self.render_trend(self.filtered_txs()))

        # Transaction list + form container so the form stays visible on smaller windows
        lower = ttk.Frame(self.root, padding=0)
        lower.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        lower.columnconfigure(0, weight=1)
        lower.rowconfigure(0, weight=1)  # list area stretches first

        list_frame = ttk.Frame(lower, padding=10)
        list_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(list_frame, text="Transactions (newest first)", style="Header.TLabel").pack(anchor="w")
        self.tx_list = tk.Listbox(list_frame, height=12, font=("Menlo", 11), bg="#0f1629", fg="#e6edff", selectbackground="#3fe0a8", borderwidth=0, highlightthickness=1, highlightbackground="#1f2d4a", selectmode=tk.EXTENDED, exportselection=False)
        self.tx_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=6)
        scroll = ttk.Scrollbar(list_frame, command=self.tx_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tx_list.config(yscrollcommand=scroll.set)
        ttk.Button(list_frame, text="Delete Selected", command=self.delete_selected_transactions).pack(anchor="e", pady=(0, 4))

        form = ttk.Frame(lower, padding=10, borderwidth=1, relief=tk.GROOVE)
        form.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))

        today = date.today().strftime("%Y-%m-%d")
        self.var_date = tk.StringVar(value=today)
        self.var_amount = tk.StringVar()
        self.var_type = tk.StringVar(value="expense")
        self.var_category = tk.StringVar(value=EXPENSE_CATEGORIES[0])
        self.var_desc = tk.StringVar()


        ttk.Label(form, text="Date YYYY-MM-DD").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.var_date, width=12).grid(row=1, column=0, padx=4)

        ttk.Label(form, text="Amount").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.var_amount, width=10).grid(row=1, column=1, padx=4)

        ttk.Label(form, text="Type").grid(row=0, column=2, sticky="w")
        type_combo = ttk.Combobox(form, textvariable=self.var_type, values=["expense", "income"], state="readonly", width=10)
        type_combo.grid(row=1, column=2, padx=4)
        type_combo.bind("<<ComboboxSelected>>", lambda _: self.on_type_changed())

        ttk.Label(form, text="Category").grid(row=0, column=3, sticky="w")
        self.category_combo = ttk.Combobox(form, textvariable=self.var_category, values=categories_for_type(self.var_type.get()), state="readonly", width=14)
        self.category_combo.grid(row=1, column=3, padx=4)

        ttk.Label(form, text="Description").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.var_desc, width=28).grid(row=1, column=4, padx=4)

        ttk.Button(form, text="Add Transaction", command=self.add_transaction, style="Accent.TButton").grid(row=1, column=5, padx=8)

    def on_type_changed(self) -> None:
        categories = categories_for_type(self.var_type.get())
        self.category_combo["values"] = categories
        if self.var_category.get() not in categories:
            self.var_category.set(categories[0])

    def current_txs(self) -> List[Transaction]:
        return self.accounts[self.active_account.get()]

    def filtered_tx_rows(self) -> List[Tuple[int, Transaction]]:
        rows = list(enumerate(self.current_txs()))
        sel = self.month_filter.get()
        if sel == "All Months":
            return rows
        return [(idx, tx) for idx, tx in rows if month_key(str(tx.get("date", ""))) == sel]

    def filtered_txs(self) -> List[Transaction]:
        return [tx for _, tx in self.filtered_tx_rows()]

    def refresh(self) -> None:
        visible_rows = sorted(self.filtered_tx_rows(), key=lambda item: item[1].get("date", ""), reverse=True)
        self.visible_tx_indices = [idx for idx, _ in visible_rows]
        txs = [tx for _, tx in visible_rows]
        self.refresh_month_options()
        # Summary text
        s = summarize(txs, month_selector=self.month_filter.get())
        self.summary_var.set(
            f"Balance {s['balance']:.2f} | Income {s['income']:.2f} | Spent {s['spent']:.2f} | 7d Spent {s['spent_week']:.2f} | Subscriptions {s['spent_subs']:.2f}"
        )
        self.forecast_var.set(
            f"Month spent {s['spent_month']:.2f}, projected {s['projected']:.2f} ({s['day']}/{s['dim']} days)"
        )

        # Listbox
        self.tx_list.delete(0, tk.END)
        for t in txs:
            if t.get("type") == "expense":
                sign = "-"
            elif t.get("type") == "income":
                sign = "+"
            else:
                sign = "?"
            flags = [str(flag) for flag in t.get(MISSING_FLAGS_KEY, []) if str(flag).strip()]
            if "missing category" in flags:
                marker = "[MISSING CATEGORY] "
            elif flags:
                marker = "[INCOMPLETE] "
            else:
                marker = ""
            # Align columns for readability (date | amount | category | description)
            line = f"{t.get('date',''):<12} {sign}{float(t.get('amount',0)):>10.2f}   {t.get('category',''):<24}   {marker}{t.get('description','')}"
            self.tx_list.insert(tk.END, line)

        # Update account combo values
        self.account_combo["values"] = list(self.accounts.keys())
        self.refresh_trend_category_options()
        self.render_categories(txs)
        self.render_insights(txs)
        self.render_trend(txs)

    def refresh_month_options(self) -> None:
        txs = self.current_txs()
        months = sorted({month_key(str(t.get("date", ""))) for t in txs if month_key(str(t.get("date", "")))} , reverse=True)
        values = ["All Months"] + months
        self.month_combo["values"] = values
        if self.month_filter.get() not in values:
            self.month_filter.set("All Months")

    def clear_frame(self, frame: ttk.Frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def refresh_trend_category_options(self) -> None:
        categories = sorted({
            str(t.get("category", "Other"))
            for t in self.current_txs()
            if t.get("type") == "expense"
        })
        values = ["All Categories"] + categories
        self.trend_category_combo["values"] = values
        if self.trend_category.get() not in values:
            self.trend_category.set("All Categories")

    def render_categories(self, txs: List[Transaction]) -> None:
        self.clear_frame(self.cat_body)
        top = category_breakdown(txs)
        if not top:
            ttk.Label(self.cat_body, text="No expense records", foreground="#9bb0d1").pack(anchor="w")
            return
        total = sum(v for _, v in top) or 1
        for cat, amt in top[:6]:
            pct = (amt / total) * 100
            row = ttk.Frame(self.cat_body)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=cat, font=("Helvetica Neue", 12, "bold")).pack(side=tk.LEFT)
            ttk.Label(row, text=f"{format_currency(amt)} · {pct:.0f}%", foreground="#9bb0d1").pack(side=tk.RIGHT)
            bar = ttk.Progressbar(self.cat_body, style="Accent.Horizontal.TProgressbar", maximum=100, value=pct)
            bar.pack(fill=tk.X, pady=(0, 6))

    def render_insights(self, txs: List[Transaction]) -> None:
        self.clear_frame(self.insight_body)

        # Spending alert banner
        alert = self._get_spending_alert(self.current_txs())
        if alert:
            warn = ttk.Frame(self.insight_body, padding=(8, 6, 8, 6))
            warn.pack(fill=tk.X, pady=(0, 4))
            ttk.Label(warn, text=f"⚠  Spending Alert — {alert['month']}",
                      foreground="#ffb347", font=("Helvetica Neue", 11, "bold")).pack(anchor="w")
            ttk.Label(warn,
                      text=f"This month: {format_currency(alert['cur'])}   Historical avg: {format_currency(alert['avg'])}",
                      foreground="#ffb347").pack(anchor="w")
            if alert["over_cats"]:
                ttk.Label(warn, text="Abnormal categories:",
                          foreground="#ffb347", font=("Helvetica Neue", 10, "bold")).pack(anchor="w", pady=(4, 0))
                for cat, val, excess in alert["over_cats"]:
                    ttk.Label(warn,
                              text=f"  • {cat}  {format_currency(val)}  (+{format_currency(excess)} above avg)",
                              foreground="#ff9999").pack(anchor="w")
            ttk.Separator(self.insight_body, orient="horizontal").pack(fill=tk.X, pady=(4, 6))

        total_income = sum(float(t.get("amount", 0)) for t in txs if t.get("type") == "income")
        total_expense = sum(float(t.get("amount", 0)) for t in txs if t.get("type") == "expense")
        net = total_income - total_expense

        # Income / Expense summary block
        summary_block = ttk.Frame(self.insight_body, padding=8)
        summary_block.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(summary_block, text="Income vs Expense", font=("Helvetica Neue", 12, "bold")).pack(anchor="w")
        inc_row = ttk.Frame(summary_block)
        inc_row.pack(fill=tk.X, pady=2)
        ttk.Label(inc_row, text="Total Income:", width=16, anchor="w").pack(side=tk.LEFT)
        ttk.Label(inc_row, text=format_currency(total_income), foreground="#3fe0a8", font=("Helvetica Neue", 12, "bold")).pack(side=tk.LEFT)
        exp_row = ttk.Frame(summary_block)
        exp_row.pack(fill=tk.X, pady=2)
        ttk.Label(exp_row, text="Total Expense:", width=16, anchor="w").pack(side=tk.LEFT)
        ttk.Label(exp_row, text=format_currency(total_expense), foreground="#ff6b6b", font=("Helvetica Neue", 12, "bold")).pack(side=tk.LEFT)
        net_row = ttk.Frame(summary_block)
        net_row.pack(fill=tk.X, pady=2)
        ttk.Label(net_row, text="Net:", width=16, anchor="w").pack(side=tk.LEFT)
        net_color = "#3fe0a8" if net >= 0 else "#ff6b6b"
        ttk.Label(net_row, text=format_currency(net), foreground=net_color, font=("Helvetica Neue", 12, "bold")).pack(side=tk.LEFT)

        ttk.Separator(self.insight_body, orient="horizontal").pack(fill=tk.X, pady=6)

        expense = [t for t in txs if t.get("type") == "expense"]
        if not expense:
            ttk.Label(self.insight_body, text="No expense data", foreground="#9bb0d1").pack(anchor="w")
            return
        top = category_breakdown(expense)
        top_cat, top_val = top[0]
        avg_ticket = sum(t["amount"] for t in expense) / max(len(expense), 1)

        pills = [
            f"Top spending category: {top_cat} ({format_currency(top_val)})",
            f"Average expense: {format_currency(avg_ticket)}",
            f"Records: {len(txs)} entries",
        ]
        for text in pills:
            pill = ttk.Frame(self.insight_body, padding=8)
            pill.pack(fill=tk.X, pady=4)
            ttk.Label(pill, text=text).pack(anchor="w")

    def _get_spending_alert(self, all_txs: List[Transaction]):
        """Return alert info dict if current/selected month expense exceeds historical average."""
        today = date.today()
        sel = self.month_filter.get()
        check_month = sel if (sel != "All Months" and sel) else today.strftime("%Y-%m")

        monthly: Dict[str, float] = {}
        for t in all_txs:
            if t.get("type") != "expense":
                continue
            mk = month_key(str(t.get("date", "")))
            if mk:
                monthly[mk] = monthly.get(mk, 0) + float(t.get("amount", 0))

        if check_month not in monthly or len(monthly) < 2:
            return None

        other = {k: v for k, v in monthly.items() if k < check_month}
        if not other:
            return None
        avg = sum(other.values()) / len(other)
        cur = monthly[check_month]
        if cur <= avg:
            return None

        # Per-category breakdown for each month
        cat_by_month: Dict[str, Dict[str, float]] = {}
        for t in all_txs:
            if t.get("type") != "expense":
                continue
            mk = month_key(str(t.get("date", "")))
            if not mk:
                continue
            cat = str(t.get("category", "Other"))
            if mk not in cat_by_month:
                cat_by_month[mk] = {}
            cat_by_month[mk][cat] = cat_by_month[mk].get(cat, 0) + float(t.get("amount", 0))

        n = len(other)
        cat_avg: Dict[str, float] = {}
        for m in other:
            for cat, val in cat_by_month.get(m, {}).items():
                cat_avg[cat] = cat_avg.get(cat, 0) + val
        cat_avg = {k: v / n for k, v in cat_avg.items()}

        check_cats = cat_by_month.get(check_month, {})
        over_cats = []
        for cat, val in check_cats.items():
            excess = val - cat_avg.get(cat, 0)
            if excess > 0:
                over_cats.append((cat, val, excess))
        over_cats.sort(key=lambda x: x[2], reverse=True)

        return {
            "month": check_month,
            "cur": cur,
            "avg": avg,
            "over_cats": over_cats,
        }

    def render_trend(self, txs: List[Transaction]) -> None:
        canvas = self.trend_canvas
        canvas.delete("all")
        W = canvas.winfo_width()
        H = canvas.winfo_height()
        if W <= 1:
            self.root.after(50, lambda: self.render_trend(txs))
            return

        expense_txs = [t for t in txs if t.get("type") == "expense"]
        selected_category = self.trend_category.get()
        sel = self.month_filter.get()
        if sel != "All Months" and sel:
            if selected_category == "All Categories":
                self._render_month_category_trend(expense_txs, W, H, sel)
            else:
                self._render_daily_category_trend(expense_txs, W, H, selected_category)
        else:
            self._render_trend_line(expense_txs, W, H, selected_category)

    def _render_month_category_trend(self, txs: List[Transaction], W: int, H: int, month: str) -> None:
        canvas = self.trend_canvas
        category_totals: Dict[str, float] = {}
        for t in txs:
            cat = str(t.get("category", "Other"))
            category_totals[cat] = category_totals.get(cat, 0) + float(t.get("amount", 0))

        if not category_totals:
            canvas.create_text(W // 2, H // 2, text="No data for this month",
                               fill="#9bb0d1", font=("Helvetica Neue", 12))
            return

        pad_l, pad_r, pad_t, pad_b = 68, 20, 20, 36
        ch = H - pad_t - pad_b
        cw = W - pad_l - pad_r
        items = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        max_val = max((amount for _, amount in items), default=1)

        for i in range(5):
            gy = pad_t + ch - (i / 4) * ch
            gv = (i / 4) * max_val
            canvas.create_line(pad_l, gy, W - pad_r, gy, fill="#1f2d4a", dash=(4, 4))
            canvas.create_text(pad_l - 6, gy, text=f"{gv:.0f}",
                               anchor="e", fill="#9bb0d1", font=("Helvetica Neue", 9))

        count = len(items)
        slot_w = cw / max(count, 1)
        bar_w = max(min(slot_w * 0.55, 72), 18)
        for idx, (label, val) in enumerate(items):
            bx = pad_l + slot_w * idx + (slot_w - bar_w) / 2
            bh = (val / max_val) * ch
            by = pad_t + ch - bh
            canvas.create_rectangle(bx, by, bx + bar_w, pad_t + ch, fill="#ff6b6b", outline="")
            canvas.create_text(bx + bar_w / 2, pad_t + ch + 12, text=label,
                               fill="#9bb0d1", font=("Helvetica Neue", 10))
            canvas.create_text(bx + bar_w / 2, by - 10, text=f"{val:.0f}",
                               fill="#ff6b6b", font=("Helvetica Neue", 9, "bold"))

        canvas.create_text(pad_l, 8, text=f"{month} category spending",
                           anchor="w", fill="#d9e5ff", font=("Helvetica Neue", 10, "bold"))

    def _render_daily_category_trend(self, txs: List[Transaction], W: int, H: int, category: str) -> None:
        canvas = self.trend_canvas
        daily_spending: Dict[str, float] = {}
        for t in txs:
            if str(t.get("category", "Other")) != category:
                continue
            day = str(t.get("date", ""))
            daily_spending[day] = daily_spending.get(day, 0) + float(t.get("amount", 0))

        days = sorted(daily_spending.keys())
        if not days:
            canvas.create_text(W // 2, H // 2, text=f"No {category} spending in this month",
                               fill="#9bb0d1", font=("Helvetica Neue", 12))
            return

        pad_l, pad_r, pad_t, pad_b = 68, 20, 20, 36
        ch = H - pad_t - pad_b
        cw = W - pad_l - pad_r
        max_val = max(daily_spending.values(), default=1)

        for i in range(5):
            gy = pad_t + ch - (i / 4) * ch
            gv = (i / 4) * max_val
            canvas.create_line(pad_l, gy, W - pad_r, gy, fill="#1f2d4a", dash=(4, 4))
            canvas.create_text(pad_l - 6, gy, text=f"{gv:.0f}",
                               anchor="e", fill="#9bb0d1", font=("Helvetica Neue", 9))

        xs = [pad_l + (i / max(len(days) - 1, 1)) * cw for i in range(len(days))]
        ys = [pad_t + ch - (daily_spending[day] / max_val) * ch for day in days]
        if len(days) > 1:
            coords: List[float] = []
            for x, y in zip(xs, ys):
                coords += [x, y]
            canvas.create_line(*coords, fill="#ff6b6b", width=2)
        for x, y, day in zip(xs, ys, days):
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#ff6b6b", outline="#ff6b6b")
            canvas.create_text(x, H - pad_b + 10, text=day[8:],
                               fill="#9bb0d1", font=("Helvetica Neue", 9))

        canvas.create_text(pad_l, 8, text=f"{category} daily spending",
                           anchor="w", fill="#d9e5ff", font=("Helvetica Neue", 10, "bold"))

    def _render_trend_line(self, txs: List[Transaction], W: int, H: int, category: str) -> None:
        canvas = self.trend_canvas

        monthly_expense: Dict[str, float] = {}
        for t in txs:
            if category != "All Categories" and str(t.get("category", "Other")) != category:
                continue
            mk = month_key(str(t.get("date", "")))
            if not mk:
                continue
            monthly_expense[mk] = monthly_expense.get(mk, 0) + float(t.get("amount", 0))

        all_months = sorted(monthly_expense.keys())
        if not all_months:
            canvas.create_text(W // 2, H // 2, text="No data to display",
                               fill="#9bb0d1", font=("Helvetica Neue", 12))
            return

        pad_l, pad_r, pad_t, pad_b = 68, 20, 16, 36
        cw = W - pad_l - pad_r
        ch = H - pad_t - pad_b
        n = len(all_months)

        exp_vals = [monthly_expense.get(m, 0) for m in all_months]
        max_val = max(max(exp_vals), 1)

        for i in range(5):
            gy = pad_t + ch - (i / 4) * ch
            gv = (i / 4) * max_val
            canvas.create_line(pad_l, gy, W - pad_r, gy, fill="#1f2d4a", dash=(4, 4))
            canvas.create_text(pad_l - 6, gy, text=f"{gv:.0f}",
                               anchor="e", fill="#9bb0d1", font=("Helvetica Neue", 9))

        xs = [pad_l + (i / max(n - 1, 1)) * cw for i in range(n)]

        for i, (m, x) in enumerate(zip(all_months, xs)):
            label = m[5:]
            if i == 0 or all_months[i][:4] != all_months[i - 1][:4]:
                label = m
            canvas.create_text(x, H - pad_b + 10, text=label,
                               fill="#9bb0d1", font=("Helvetica Neue", 9))

        ys = [pad_t + ch - (v / max_val) * ch for v in exp_vals]
        if n > 1:
            coords: List[float] = []
            for x, y in zip(xs, ys):
                coords += [x, y]
            canvas.create_line(*coords, fill="#ff6b6b", width=2)
        for x, y, v in zip(xs, ys, exp_vals):
            if v > 0:
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#ff6b6b", outline="#ff6b6b")

        title = "Overall monthly spending" if category == "All Categories" else f"{category} monthly spending"
        canvas.create_text(pad_l, 8, text=title,
                           anchor="w", fill="#d9e5ff", font=("Helvetica Neue", 10, "bold"))

    def add_transaction(self) -> None:
        try:
            amt = float(self.var_amount.get())
        except Exception:
            messagebox.showerror("Error", "Amount must be numeric")
            return
        date_str = self.var_date.get().strip()
        if not date_str:
            messagebox.showerror("Error", "Date is required")
            return
        self.current_txs().append({
            "date": date_str,
            "amount": amt,
            "type": self.var_type.get(),
            "category": self.var_category.get(),
            "description": self.var_desc.get().strip() or "Manual",
            "method": "Manual",
        })
        self.var_amount.set("")
        self.var_desc.set("")
        self.on_type_changed()
        self.refresh()
    
    #delete transactions
    def delete_selected_transactions(self) -> None:
        selected = self.tx_list.curselection()
        if not selected:
            messagebox.showwarning("Delete", "Select at least one transaction to delete")
            return

        count = len(selected)
        confirmed = messagebox.askyesno("Delete", f"Delete {count} selected transaction(s)?")
        if not confirmed:
            return

        current = self.current_txs()
        for list_index in sorted(selected, reverse=True):
            tx_index = self.visible_tx_indices[list_index]
            del current[tx_index]

        self.refresh()

    def import_file(self) -> None:
        path_str = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("All", "*.*")])
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() == ".json":
            new_rows, stats = load_json(path)
        else:
            new_rows, stats = load_csv(path)
        if not new_rows:
            messagebox.showwarning("Import", summarize_import(stats) or "No valid data parsed")
            return
        self.current_txs().extend(new_rows)
        messagebox.showinfo("Import", summarize_import(stats))
        self.refresh()

    def export_file(self) -> None:
        path_str = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="transactions.csv")
        if not path_str:
            return
        export_csv(Path(path_str), self.current_txs())
        messagebox.showinfo("Export", f"Saved to {path_str}")

    def create_account(self) -> None:
        name = simpledialog.askstring("New account", "Enter account name")
        if not name:
            return
        if name in self.accounts:
            messagebox.showwarning("Notice", "Account already exists")
            return
        self.accounts[name] = []
        self.active_account.set(name)
        self.refresh()


def main() -> None:
    root = tk.Tk()
    FinanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
