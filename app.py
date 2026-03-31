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
CATEGORIES = ["Meals", "Transport", "Subscriptions", "Groceries", "Fun", "Utilities", "Income", "Other"]

DEFAULT_ACCOUNTS: Dict[str, List[Dict[str, object]]] = {
    "Case A": [],
    "Case B": [],
    "Case C": [],
    "Case D": [],
}

Transaction = Dict[str, object]


def format_currency(amount: float) -> str:
    return f"¥{amount:.2f}"


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


def days_in_month(d: date) -> int:
    next_month = d.replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).day


def load_csv(path: Path) -> List[Transaction]:
    rows: List[Transaction] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header: List[str] = []
        for idx, cols in enumerate(reader):
            if not cols or all(not c.strip() for c in cols):
                continue
            if idx == 0:
                header = [c.strip().lower() for c in cols]
                # Decide whether this is a header row by checking typical column names
                if any(h in header for h in ["date", "amount", "amount in hkd", "category", "description"]):
                    continue  # treat as header
            # Map columns by position with header hints
            def pick(col_names: List[str], default_index: int | None = None) -> str:
                for name in col_names:
                    if name in header:
                        return cols[header.index(name)].strip()
                if default_index is not None and default_index < len(cols):
                    return cols[default_index].strip()
                return ""

            raw_date = pick(["date"], 0)
            raw_amount = pick(["amount", "amount in hkd"], 1)
            raw_type = pick(["type"], None) or "expense"
            raw_category = pick(["category"], 3) or "Other"
            raw_desc = pick(["description", "memo"], 4) or "Imported"
            raw_method = pick(["method", "payment"], 5) or "Imported"

            # Clean amount: remove currency symbols/commas
            amt_clean = raw_amount.replace("$", "").replace(",", "").strip()
            try:
                amount = float(amt_clean)
                if not raw_date:
                    raise ValueError("missing date")
                date_obj = parse_date_safe(raw_date)
            except Exception:
                print(f"[skip] invalid row {idx + 1}: {cols}")
                continue

            tx_type = raw_type.lower() if isinstance(raw_type, str) else "expense"
            if tx_type not in ("expense", "income"):
                tx_type = "expense"

            rows.append({
                "date": date_obj.strftime("%Y-%m-%d"),
                "amount": amount,
                "type": tx_type,
                "category": raw_category or "Other",
                "description": raw_desc or "Imported",
                "method": raw_method or "Imported",
            })
    return rows


def load_json(path: Path) -> List[Transaction]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        messagebox.showerror("导入失败", "JSON 顶层必须是数组")
        return []
    rows: List[Transaction] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            print(f"[skip] invalid item #{idx + 1}: {item}")
            continue
        date_str = str(item.get("date", "")).strip()
        try:
            amount = float(item.get("amount", ""))
        except Exception:
            print(f"[skip] invalid amount in item #{idx + 1}: {item}")
            continue
        if not date_str:
            print(f"[skip] missing date in item #{idx + 1}")
            continue
        rows.append({
            "date": date_str,
            "amount": amount,
            "type": str(item.get("type", "expense")),
            "category": str(item.get("category", "Other")),
            "description": str(item.get("description", "Imported")),
            "method": str(item.get("method", "Imported")),
        })
    return rows


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


def summarize(txs: List[Transaction], month_selector: str = "全部月份") -> Dict[str, float]:
    spent = sum(t["amount"] for t in txs if t.get("type") == "expense")
    income = sum(t["amount"] for t in txs if t.get("type") == "income")
    balance = income - spent
    today = date.today()

    # Month selection handling
    if month_selector != "全部月份" and month_selector:
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
        self.month_filter: tk.StringVar = tk.StringVar(value="全部月份")

        self.summary_var = tk.StringVar()
        self.forecast_var = tk.StringVar()

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

        ttk.Label(top, text="账号:").pack(side=tk.LEFT)
        self.account_combo = ttk.Combobox(top, textvariable=self.active_account, values=list(self.accounts.keys()), width=18, state="readonly")
        self.account_combo.pack(side=tk.LEFT, padx=6)
        self.account_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        ttk.Button(top, text="新账号", command=self.create_account).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="导入 CSV/JSON", command=self.import_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="导出 CSV", command=self.export_file).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="月份:").pack(side=tk.LEFT, padx=(16, 4))
        self.month_combo = ttk.Combobox(top, textvariable=self.month_filter, values=["全部月份"], width=12, state="readonly")
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
        ttk.Label(self.cat_frame, text="分类走向", style="Header.TLabel").pack(anchor="w")
        self.cat_body = ttk.Frame(self.cat_frame)
        self.cat_body.pack(fill=tk.BOTH, expand=True, pady=6)

        self.insight_frame = ttk.Frame(analytics, padding=10, borderwidth=1, relief=tk.GROOVE)
        self.insight_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        ttk.Label(self.insight_frame, text="洞察 / 快速提示", style="Header.TLabel").pack(anchor="w")
        self.insight_body = ttk.Frame(self.insight_frame)
        self.insight_body.pack(fill=tk.BOTH, expand=True, pady=6)

        # Transaction list + form container so the form stays visible on smaller windows
        lower = ttk.Frame(self.root, padding=0)
        lower.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        lower.columnconfigure(0, weight=1)
        lower.rowconfigure(0, weight=1)  # list area stretches first

        list_frame = ttk.Frame(lower, padding=10)
        list_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(list_frame, text="流水 (按日期倒序)", style="Header.TLabel").pack(anchor="w")
        self.tx_list = tk.Listbox(list_frame, height=12, font=("Menlo", 11), bg="#0f1629", fg="#e6edff", selectbackground="#3fe0a8", borderwidth=0, highlightthickness=1, highlightbackground="#1f2d4a")
        self.tx_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=6)
        scroll = ttk.Scrollbar(list_frame, command=self.tx_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tx_list.config(yscrollcommand=scroll.set)

        form = ttk.Frame(lower, padding=10, borderwidth=1, relief=tk.GROOVE)
        form.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))

        today = date.today().strftime("%Y-%m-%d")
        self.var_date = tk.StringVar(value=today)
        self.var_amount = tk.StringVar()
        self.var_type = tk.StringVar(value="expense")
        self.var_category = tk.StringVar(value="Meals")
        self.var_desc = tk.StringVar()
        self.var_method = tk.StringVar(value="Manual")

        ttk.Label(form, text="日期 YYYY-MM-DD").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.var_date, width=12).grid(row=1, column=0, padx=4)

        ttk.Label(form, text="金额").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.var_amount, width=10).grid(row=1, column=1, padx=4)

        ttk.Label(form, text="类型").grid(row=0, column=2, sticky="w")
        ttk.Combobox(form, textvariable=self.var_type, values=["expense", "income"], state="readonly", width=10).grid(row=1, column=2, padx=4)

        ttk.Label(form, text="分类").grid(row=0, column=3, sticky="w")
        ttk.Combobox(form, textvariable=self.var_category, values=CATEGORIES, state="readonly", width=14).grid(row=1, column=3, padx=4)

        ttk.Label(form, text="描述").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.var_desc, width=28).grid(row=1, column=4, padx=4)

        ttk.Label(form, text="方式").grid(row=0, column=5, sticky="w")
        ttk.Entry(form, textvariable=self.var_method, width=12).grid(row=1, column=5, padx=4)

        ttk.Button(form, text="添加流水", command=self.add_transaction, style="Accent.TButton").grid(row=1, column=6, padx=8)

    def current_txs(self) -> List[Transaction]:
        return self.accounts[self.active_account.get()]

    def filtered_txs(self) -> List[Transaction]:
        txs = self.current_txs()
        sel = self.month_filter.get()
        if sel == "全部月份":
            return txs
        return [t for t in txs if month_key(str(t.get("date", ""))) == sel]

    def refresh(self) -> None:
        txs = self.filtered_txs()
        self.refresh_month_options()
        # Summary text
        s = summarize(txs, month_selector=self.month_filter.get())
        self.summary_var.set(
            f"余额 {s['balance']:.2f} | 收入 {s['income']:.2f} | 支出 {s['spent']:.2f} | 7日支出 {s['spent_week']:.2f} | 订阅 {s['spent_subs']:.2f}"
        )
        self.forecast_var.set(
            f"本月已用 {s['spent_month']:.2f}，按当前日均预计 {s['projected']:.2f}（{s['day']}/{s['dim']} 天）"
        )

        # Listbox
        self.tx_list.delete(0, tk.END)
        for t in sorted(txs, key=lambda x: x.get("date", ""), reverse=True):
            sign = "-" if t.get("type") == "expense" else "+"
            # Align columns for readability (date | amount | category | description)
            line = f"{t.get('date',''):<12} {sign}{float(t.get('amount',0)):>10.2f}   {t.get('category',''):<14}   {t.get('description','')}"
            self.tx_list.insert(tk.END, line)

        # Update account combo values
        self.account_combo["values"] = list(self.accounts.keys())
        self.render_categories(txs)
        self.render_insights(txs)

    def refresh_month_options(self) -> None:
        txs = self.current_txs()
        months = sorted({month_key(str(t.get("date", ""))) for t in txs if month_key(str(t.get("date", "")))} , reverse=True)
        values = ["全部月份"] + months
        self.month_combo["values"] = values
        if self.month_filter.get() not in values:
            self.month_filter.set("全部月份")

    def clear_frame(self, frame: ttk.Frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def render_categories(self, txs: List[Transaction]) -> None:
        self.clear_frame(self.cat_body)
        top = category_breakdown(txs)
        if not top:
            ttk.Label(self.cat_body, text="暂无支出记录", foreground="#9bb0d1").pack(anchor="w")
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
        expense = [t for t in txs if t.get("type") == "expense"]
        if not expense:
            ttk.Label(self.insight_body, text="暂无数据", foreground="#9bb0d1").pack(anchor="w")
            return
        top = category_breakdown(expense)
        top_cat, top_val = top[0]
        avg_ticket = sum(t["amount"] for t in expense) / max(len(expense), 1)

        pills = [
            f"最大支出类别：{top_cat} ({format_currency(top_val)})",
            f"平均单笔支出：{format_currency(avg_ticket)}",
            f"记录数：{len(txs)} 笔",
        ]
        for text in pills:
            pill = ttk.Frame(self.insight_body, padding=8)
            pill.pack(fill=tk.X, pady=4)
            ttk.Label(pill, text=text).pack(anchor="w")

    def add_transaction(self) -> None:
        try:
            amt = float(self.var_amount.get())
        except Exception:
            messagebox.showerror("错误", "金额必须为数字")
            return
        date_str = self.var_date.get().strip()
        if not date_str:
            messagebox.showerror("错误", "日期不能为空")
            return
        self.current_txs().append({
            "date": date_str,
            "amount": amt,
            "type": self.var_type.get(),
            "category": self.var_category.get(),
            "description": self.var_desc.get().strip() or "Manual",
            "method": self.var_method.get().strip() or "Manual",
        })
        self.var_amount.set("")
        self.var_desc.set("")
        self.refresh()

    def import_file(self) -> None:
        path_str = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("All", "*.*")])
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() == ".json":
            new_rows = load_json(path)
        else:
            new_rows = load_csv(path)
        if not new_rows:
            messagebox.showwarning("导入", "未解析到有效数据")
            return
        self.current_txs().extend(new_rows)
        messagebox.showinfo("导入", f"成功导入 {len(new_rows)} 条")
        self.refresh()

    def export_file(self) -> None:
        path_str = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="transactions.csv")
        if not path_str:
            return
        export_csv(Path(path_str), self.current_txs())
        messagebox.showinfo("导出", f"已保存到 {path_str}")

    def create_account(self) -> None:
        name = simpledialog.askstring("新账号", "输入账号名称")
        if not name:
            return
        if name in self.accounts:
            messagebox.showwarning("提示", "该账号已存在")
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
