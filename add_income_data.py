#!/usr/bin/env python3
"""One-shot script: add a 'type' column and income rows to the two spending CSVs."""

import csv
import random
from pathlib import Path

random.seed(42)

STUDENT_INCOME = [
    ("2026/1/1",  5000, "Monthly allowance from parents"),
    ("2026/1/15", 8000, "HKU scholarship Q1"),
    ("2026/1/20",  800, "Part-time tutoring"),
    ("2026/2/1",  5000, "Monthly allowance from parents"),
    ("2026/2/12", 1000, "Campus job"),
    ("2026/2/25",  700, "Part-time tutoring"),
    ("2026/3/1",  5000, "Monthly allowance from parents"),
    ("2026/3/8",   900, "Part-time tutoring"),
]

WORKER_INCOME = [
    ("2026/1/25", 25000, "Monthly salary"),
    ("2026/2/10",   800, "Expense reimbursement"),
    ("2026/2/25", 25000, "Monthly salary"),
    ("2026/2/28", 30000, "Year-end bonus"),
    ("2026/3/5",   1200, "Expense reimbursement"),
]

OUTPUT_COLS = ["transaction_id", "date", "amount in HKD", "type", "category", "description"]


def parse_date_sort_key(d: str) -> tuple:
    """Parse 'YYYY/M/D' into a tuple for sorting."""
    parts = d.split("/")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def jitter(base: float) -> str:
    """Apply +/-2% random jitter and format to 2 decimal places."""
    return f"${random.uniform(base * 0.98, base * 1.02):,.2f}"


def process(csv_path: Path, income_rows: list) -> None:
    # Read existing data rows (skip header)
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Detect column indices from the original header
        norm = [c.strip().lower().replace(" ", "_") for c in header]
        id_idx = norm.index("transaction_id")
        date_idx = norm.index("date")
        # Amount column: try several names
        amt_idx = None
        for name in ["amount_in_hkd", "amount_in_hkd", "amountinhkd"]:
            if name in norm:
                amt_idx = norm.index(name)
                break
        if amt_idx is None:
            # fallback: look for partial match
            for i, n in enumerate(norm):
                if "amount" in n:
                    amt_idx = i
                    break
        cat_idx = norm.index("category")
        desc_idx = norm.index("description")

        existing = []
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            existing.append({
                "date": row[date_idx].strip(),
                "amount": row[amt_idx].strip(),
                "type": "expense",
                "category": row[cat_idx].strip(),
                "description": row[desc_idx].strip(),
            })

    # Build income rows with jittered amounts
    income_total = 0.0
    for date_str, base_amt, desc in income_rows:
        amt_val = round(random.uniform(base_amt * 0.98, base_amt * 1.02), 2)
        income_total += amt_val
        existing.append({
            "date": date_str,
            "amount": f"${amt_val:,.2f}",
            "type": "income",
            "category": "Income",
            "description": desc,
        })

    # Sort by date
    existing.sort(key=lambda r: parse_date_sort_key(r["date"]))

    # Reassign transaction_id
    for i, row in enumerate(existing, 1):
        row["transaction_id"] = str(i)

    # Write back
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLS)
        for row in existing:
            writer.writerow([
                row["transaction_id"],
                row["date"],
                row["amount"],
                row["type"],
                row["category"],
                row["description"],
            ])

    print(f"{csv_path.name}: added {len(income_rows)} income rows, "
          f"new total = {len(existing)} rows, "
          f"income total = ${income_total:,.2f}")


if __name__ == "__main__":
    process(Path("student_spending_2026_q1.csv"), STUDENT_INCOME)
    process(Path("worker_spending_2026_q1.csv"), WORKER_INCOME)
    print("Done.")
