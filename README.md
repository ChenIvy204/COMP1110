# Personal Budget and Spending Assistant

> A lightweight, privacy-first desktop application for personal finance tracking.
>
> COMP1110 Computing and Data Science in Everyday Life · Topic A · Group Project · Semester 2 2025-26

## Overview

This project helps students and working professionals track daily spending, identify abnormal consumption patterns, and understand where their money goes each month. It targets two common pain points: fragmented spending records scattered across payment apps, and the lack of category-level analysis that makes it hard to spot creeping expenses like subscriptions or impulse buys.

The application runs entirely on the local machine with no cloud sync, no accounts to create, and no third-party dependencies. All data stays in CSV files on your disk. This local-only, privacy-first design means users never have to worry about financial data leaving their device.

**Tech stack**: Python 3.10+ standard library only. The GUI is built with Tkinter (ships with Python). No `pip install` required.

## Key Features

### Account Management
- Multi-account support (4 default cases + unlimited custom accounts)
- Independent transaction data per account
- One-click account switching via dropdown

### Data I/O
- Import from CSV or JSON files with automatic header alias detection (handles column names like `amount_in_hkd`, `transaction_id`, `memo`, etc.)
- Automatic data repair during import: missing dates filled from previous row, missing amounts set to zero, unrecognised categories flagged as `[MISSING CATEGORY]`
- Import summary shows counts of imported, skipped, flagged, and repaired records
- Export current account to CSV

### Transaction Management
- Manual entry form with date, amount, category, and description fields
- Transaction type (`income` / `expense`) inferred automatically from category
- Multi-select deletion with confirmation dialog
- Per-month filter dropdown
- Visual markers in transaction list: `[INCOMPLETE]` and `[MISSING CATEGORY]` for flagged records

### Analytics
- **Income vs Expense summary** with HKD amounts and CNY equivalents
- **Category breakdown** with percentage progress bars for all expense categories
- **Monthly Income vs Expense** trend chart (dual-line graph)
- **Per-category monthly trend** chart with category selector
- **Insights panel**: top spending category, average expense amount, total record count
- **Monthly forecast**: projects full-month spending from current pace

### Smart Alerts
- Per-category thresholds tuned to spending volatility (e.g., Meals +12%, Shopping +25%)
- Compares selected month to the average of all other months
- Only alerts on upward deviation (overspending) — underspending is not flagged
- Overall spending alert at +15% as a fallback

### Multi-Currency Display
- HKD-to-CNY conversion shown in the Insights panel (Total Income, Total Expense, Net)
- Average Q1 2026 exchange rate displayed in the bottom status bar
- Source: 90 daily rates from `hkd2cny_2026_q1.csv`
- Graceful fallback: if exchange rate file is missing, CNY display is hidden

## Project Structure

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 1148 | Main application — GUI layout, data import/export, analytics, alerts, charting |
| `student_spending_2026_q1.csv` | 317 | Student persona sample data: 308 expenses + 8 income entries (Q1 2026, HKD) |
| `worker_spending_2026_q1.csv` | 390 | Worker persona sample data: 384 expenses + 5 income entries (Q1 2026, HKD) |
| `hkd2cny_2026_q1.csv` | 90 | Daily HKD-to-CNY exchange rates for Q1 2026 (90 data rows + header) |
| `add_income_data.py` | 121 | One-shot utility script used to inject income rows and `type` column into spending CSVs |
| `README.md` | — | This file |

### CSV Column Format

Both spending CSVs share the same structure:

```
transaction_id, date, amount in HKD, type, category, description
```

- `type`: `expense` or `income`
- `date`: `YYYY/M/D` format (e.g., `2026/1/15`)
- `amount in HKD`: dollar-formatted (e.g., `$188.00` or `$5,027.89`)

The exchange rate CSV:

```
date, hkd_to_cny, cny_to_hkd
```

## Requirements

- Python 3.10 or above
- No third-party packages required
- Tkinter (included in standard Python distributions)

## Installation & Run

```bash
# Clone the repository
git clone <your-github-url>
cd <repo-name>

# Run directly — no install step required
python3 app.py
```

A GUI window titled "Everyday Finance · Python GUI" will appear.

### Platform Notes

| Platform | Notes |
|----------|-------|
| **macOS** | If you get `ModuleNotFoundError: No module named '_tkinter'`, run `brew install python-tk` |
| **Linux (Ubuntu/Debian)** | Install Tkinter: `sudo apt-get install python3-tk` |
| **Linux (Fedora)** | Install Tkinter: `sudo dnf install python3-tkinter` |
| **Windows** | Tkinter is included in the official Python installer by default |

Verify Tkinter works:

```bash
python3 -m tkinter
```

A small test window should appear. If it does, you are ready to run `app.py`.

## Quick Start (5-Step Demo)

1. **Launch**: Run `python3 app.py`
2. **Import data**: Click **Import CSV/JSON** and select `student_spending_2026_q1.csv`
3. **View summary**: The Insights panel shows Total Income, Total Expense, and Net — each with an HKD amount and a CNY equivalent in parentheses
4. **Trigger an alert**: Switch the Month dropdown to **2026-01**. A Spending Alert banner appears showing Transport (+16%, threshold +15%) and Other (+13%, threshold +8%)
5. **Explore trends**: The Trends panel shows a green (Income) vs red (Expense) line chart across Jan-Mar. Use the category dropdown to see per-category trends

## Sample Data

### Student Persona (`student_spending_2026_q1.csv`)

- **316 data rows**: 308 expenses + 8 income entries
- **Date range**: 2026-01-01 to 2026-03-09
- **Persona**: A university student tracking frequent small purchases
- **Income sources**: Monthly allowance from parents (~HK$5,000), part-time tutoring (~HK$700-900), HKU scholarship Q1 (~HK$8,000), campus job (~HK$1,000)
- **Top expense categories**: Meals (76%), Transport (9%), Fun (9%), Other (5%)

### Worker Persona (`worker_spending_2026_q1.csv`)

- **389 data rows**: 384 expenses + 5 income entries
- **Date range**: 2026-01-01 to 2026-03-09
- **Persona**: A young professional with stable salary and fixed rent
- **Income sources**: Monthly salary (~HK$25,000 on 25th), year-end bonus (~HK$30,000 in Feb), expense reimbursements (~HK$800-1,200)
- **Top expense categories**: Accommodation (46%), Meals (34%), Transport (6%), Other (6%), Shopping (5%), Fun (2%)

### Exchange Rates (`hkd2cny_2026_q1.csv`)

- 90 daily rates covering the full Q1 2026 (Jan 1 – Mar 31)
- HKD-to-CNY range: 0.8770 – 0.8842
- Average rate used in application: **0.8814**
- Loaded at startup; displayed as reference only (all arithmetic remains in HKD)

## Category System

Six expense categories plus Income:

| Category | Alias Mapping (auto-converted on import) | Examples |
|----------|------------------------------------------|----------|
| Meals | `Food` | Restaurant, canteen, takeaway, snacks |
| Transport | `Transportation` | MTR, bus, taxi, ride-hailing |
| Shopping | `DailySupplies`, `Shop`, `Grocery`, `Groceries` | Supermarket, clothing, household items |
| Accommodation | *(direct match)* | Rent, housing |
| Fun | `Entertainment` | Cinema, KTV, concerts, games |
| Other | `Subscriptions`, `Subscription`, `Utilities`, `Utility`, `Office` | Phone bills, Netflix, gym membership, stationery |
| Income | *(direct match)* | Salary, allowance, scholarship, reimbursement |

Unrecognised category names are mapped to **Other** by default.

## Alert Rules

Alerts fire when a category's spending in the selected month exceeds the average of all other months by more than its threshold:

| Category | Threshold | Rationale |
|----------|-----------|-----------|
| Meals | +12% | High-frequency, low-volatility — small deviation is meaningful |
| Transport | +15% | Commute is mostly fixed; occasional ride-hailing causes spikes |
| Shopping | +25% | Highly elastic and impulse-buy prone; wide band avoids false alarms |
| Accommodation | +10% | Rent is rigid; small variance signals utility cost creep |
| Fun | +20% | Discretionary spending; large month-to-month swings are normal |
| Other | +8% | Subscriptions and bills should be predictable; flag surprises early |

A **global fallback** alert triggers when total monthly expense exceeds the historical average by more than **+15%**.

**Design choice**: Only upward deviations are flagged. Spending *less* than usual does not require user attention.

## Test Scenarios

These scenarios are reproducible with the bundled CSV files and correspond to the case studies in the Group Final Report.

### Scenario 1: Student — January Overspending

1. Import `student_spending_2026_q1.csv` into any account
2. Select month **2026-01**
3. **Expected**: Alert banner shows:
   - Transport: $517.50 (+16%, threshold +15%)
   - Other: $298.00 (+13%, threshold +8%)
4. **Interpretation**: Semester-start commute adjustment and Netflix/Spotify annual subscription

### Scenario 2: Student — March Subscription Creep

1. Same data, select month **2026-03**
2. **Expected**: Alert for Other (+32%, threshold +8%) due to Adobe Creative Cloud renewal ($328)
3. Meals, Transport, Fun all within normal range

### Scenario 3: Worker — March Consumption Shift

1. Import `worker_spending_2026_q1.csv` into a different account
2. Select month **2026-03**
3. **Expected**: Alerts for:
   - Shopping: $1,424.00 (+66%, threshold +25%)
   - Meals: $7,920.00 (+13%, threshold +12%)
4. Accommodation stays silent ($9,800, same every month) — validates the +10% threshold design

### Scenario 4: Worker — February Healthy Month

1. Same data, select month **2026-02**
2. **Expected**: No alerts triggered
3. **Interpretation**: The system does not over-warn; February spending is within normal ranges for all categories

## Known Limitations

- **No data persistence across sessions** — All imported data is held in memory. Export to CSV before closing if you need to keep changes.
- **Alert thresholds are not user-configurable via GUI** — Modifying thresholds requires editing the `CATEGORY_ALERT_THRESHOLDS` dictionary in `app.py`.
- **Category list is fixed** — Adding new categories requires editing the `EXPENSE_CATEGORIES` constant in source code.
- **Incomplete March data** — Sample CSVs cover only up to 2026-03-09 (not full March), which can affect month-over-month alert comparisons for March.
- **Single-currency arithmetic** — All calculations are in HKD. CNY values shown in the Insights panel are display-only conversions using the Q1 average rate (0.8814).

## Future Work

- User-configurable alert thresholds through a settings dialog
- Custom category management (add / rename / delete via the GUI)
- Persistent storage with auto-save to JSON between sessions
- Recurring transaction templates (e.g., monthly rent, subscriptions)
- Pie chart and bar chart visualizations alongside the existing line charts
- Per-day exchange rate conversion for precise cross-currency display

## Authors

Group members (COMP1110 Topic A):

- [Member 1 Name] — [Cheung HonLung]
- [Member 2 Name] — [Chen Airui]
- [Member 3 Name] — [Huang Junran]
- [Member 4 Name] — [Qiu Hau Yin]

*(Replace placeholders with actual names and roles before submission.)*

## Course Information

| | |
|---|---|
| **Course** | COMP1110 Computing and Data Science in Everyday Life |
| **Institution** | The University of Hong Kong, School of Computing and Data Science |
| **Semester** | 2025-26 Semester 2 |
| **Topic** | A — Personal Budget and Spending Assistant |
| **Submission** | May 2, 2026 |
