"""Generate worker-style finance test data with controllable randomness.

The output is intentionally close to worker_spending_2026_q1_full.csv:
- similar header shape, including extra empty columns
- mostly expense-focused daily records
- monthly fixed costs like rent
- occasional extreme spending outliers
- optional missing values for import robustness testing

Example:
	python test_data_generator.py --output random_worker_spending.csv 
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List


HEADER = ["transaction_id", "date", " amount_in_hkd ", "category", "description", "", "Total Spending", "", ""]

EXPENSE_CATEGORIES = ["Meals", "Transport", "Shopping", "Accommodation", "Fun", "Other"]
INCOME_CATEGORY = "Income"
MISSING_CATEGORY_LABEL = "Missing Category [Review]"


@dataclass(frozen=True)
class CategoryProfile:
	category: str
	weight: float
	weekday_range: tuple[float, float]
	weekend_range: tuple[float, float]
	descriptions: tuple[str, ...]


CATEGORY_PROFILES: tuple[CategoryProfile, ...] = (
	CategoryProfile(
		"Meals",
		0.48,
		(35, 130),
		(55, 360),
		(
			"Breakfast",
			"Lunch",
			"Cafe",
			"Snack and drink",
			"Dinner",
		),
	),
	CategoryProfile(
		"Transport",
		0.22,
		(18, 45),
		(35, 110),
		(
			"MTR",
			"Taxi",
			"Bus",
			"Railway",
		),
	),
	CategoryProfile(
		"Shopping",
		0.12,
		(25, 160),
		(90, 620),
		(
			"Supermarket shopping",
			"Household supplies",
			"Clothes and toiletries",
			"Seasonal shopping",
		),
	),
	CategoryProfile(
		"Accommodation",
		0.06,
		(6400, 11000),
		(6400, 11000),
		(
			"Monthly rent",
			"Short-term accommodation payment",
		),
	),
	CategoryProfile(
		"Fun",
		0.07,
		(45, 260),
		(120, 780),
		(
			"Cinema",
			"KTV",
			"Concert ticket",
			"Games and hobbies",
			"Weekend entertainment",
		),
	),
	CategoryProfile(
		"Other",
		0.05,
		(40, 240),
		(55, 320),
		(
			"Phone and subscription bill",
			"Office stationery",
			"Utilities payment",
			"Unexpected small expense",
		),
	),
)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Generate worker-style finance test data")
	parser.add_argument("--output", type=Path, default=Path("generated_worker_spending.csv"), help="CSV output path")
	parser.add_argument("--start", default="2026-01-01", help="Start date in YYYY-MM-DD")
	parser.add_argument("--months", type=int, default=5, help="Number of months to generate")
	parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output")
	parser.add_argument("--missing-rate", type=float, default=0.05, help="Probability that a record gets a missing field")
	parser.add_argument("--extreme-rate", type=float, default=0.035, help="Probability that a record becomes an extreme large expense")
	parser.add_argument("--income-rate", type=float, default=0.025, help="Probability of generating an income record on a day")
	parser.add_argument("--daily-max", type=int, default=5, help="Maximum normal transactions per day before monthly fixed items")
	return parser.parse_args()


def daterange(start: date, end: date) -> Iterable[date]:
	current = start
	while current <= end:
		yield current
		current += timedelta(days=1)


def add_months(start: date, months: int) -> date:
	year = start.year + (start.month - 1 + months) // 12
	month = (start.month - 1 + months) % 12 + 1
	return date(year, month, 1)


def weighted_profile(rng: random.Random) -> CategoryProfile:
	profiles = list(CATEGORY_PROFILES)
	weights = [profile.weight for profile in profiles]
	return rng.choices(profiles, weights=weights, k=1)[0]


def format_amount(amount: float) -> str:
	return f"${amount:,.2f}"


def monthly_summary_columns(rows: List[list[str]], month_totals: dict[str, float]) -> None:
	if not rows:
		return
	total_spending = sum(month_totals.values())
	rows[0][6] = format_amount(total_spending)
	if len(rows) > 2:
		rows[2][6] = "Monthly Spending"
	ordered_months = sorted(month_totals.keys())
	if len(rows) > 3:
		for index, month in enumerate(ordered_months[:3]):
			rows[3][6 + index] = format_amount(month_totals[month])


def maybe_extreme_amount(rng: random.Random, amount: float, category: str, extreme_rate: float) -> float:
	if rng.random() >= extreme_rate:
		return amount

	if category == "Accommodation":
		return round(amount * rng.uniform(1.15, 1.6), 2)
	if category == "Shopping":
		return round(amount * rng.uniform(3.5, 8.0), 2)
	if category == "Fun":
		return round(amount * rng.uniform(2.5, 7.0), 2)
	return round(amount * rng.uniform(2.0, 5.5), 2)


def maybe_make_missing(rng: random.Random, row: list[str], missing_rate: float) -> None:
	if rng.random() >= missing_rate:
		return

	missing_target = rng.choices(
		["amount", "category", "description", "date"],
		weights=[0.25, 0.35, 0.25, 0.15],
		k=1,
	)[0]

	if missing_target == "amount":
		row[2] = " $-   "
	elif missing_target == "category":
		row[3] = ""
	elif missing_target == "description":
		row[4] = ""
	elif missing_target == "date":
		row[1] = ""


def build_transaction_row(
	tx_id: int,
	when: date,
	amount: float,
	category: str,
	description: str,
) -> list[str]:
	return [
		str(tx_id),
		when.strftime("%Y/%-m/%-d") if hasattr(when, "strftime") else "",
		format_amount(amount),
		category,
		description,
		"",
		"",
		"",
		"",
	]


def weekday_transaction_count(rng: random.Random, current: date, daily_max: int) -> int:
	if current.weekday() < 5:
		return rng.randint(3, max(3, daily_max))
	return rng.randint(2, max(2, daily_max - 1))


def generate_income_rows(rng: random.Random, tx_id: int, current: date) -> list[list[str]]:
	rows: list[list[str]] = []
	if current.day in (1, 15) and rng.random() < 0.7:
		amount = round(rng.uniform(14000, 28000), 2)
		description = rng.choice([
			"Monthly salary",
			"Allowance from family",
			"Freelance side income",
			"Performance bonus",
		])
		rows.append(build_transaction_row(tx_id, current, amount, INCOME_CATEGORY, description))
	return rows


def generate_fixed_monthly_rows(rng: random.Random, tx_id: int, current: date) -> list[list[str]]:
	rows: list[list[str]] = []
	if current.day == 5:
		amount = round(rng.uniform(8500, 11000), 2)
		rows.append(build_transaction_row(tx_id, current, amount, "Accommodation", f"Rent ({current.strftime('%B')})"))
	if current.day in (18, 22):
		amount = round(rng.uniform(520, 980), 2)
		rows.append(build_transaction_row(tx_id + len(rows), current, amount, "Other", f"Utilities ({current.strftime('%B')})"))
	return rows


def generate_daily_rows(
	rng: random.Random,
	current: date,
	next_tx_id: int,
	daily_max: int,
	extreme_rate: float,
) -> list[list[str]]:
	rows: list[list[str]] = []
	count = weekday_transaction_count(rng, current, daily_max)
	is_weekend = current.weekday() >= 5

	for offset in range(count):
		profile = weighted_profile(rng)
		# Monthly categories should stay sparse; daily random draw remaps them unless intentionally large.
		if profile.category == "Accommodation":
			profile = next(p for p in CATEGORY_PROFILES if p.category in ("Meals", "Shopping", "Other"))
		amount_range = profile.weekend_range if is_weekend else profile.weekday_range
		amount = round(rng.uniform(*amount_range), 2)
		amount = maybe_extreme_amount(rng, amount, profile.category, extreme_rate)
		description = rng.choice(profile.descriptions)
		rows.append(build_transaction_row(next_tx_id + offset, current, amount, profile.category, description))

	return rows


def generate_rows(args: argparse.Namespace) -> list[list[str]]:
	rng = random.Random(args.seed)
	start = date.fromisoformat(args.start)
	end = add_months(start, args.months) - timedelta(days=1)

	rows: list[list[str]] = []
	tx_id = 1
	month_totals: dict[str, float] = {}

	for current in daterange(start, end):
		day_rows: list[list[str]] = []

		fixed_rows = generate_fixed_monthly_rows(rng, tx_id, current)
		tx_id += len(fixed_rows)
		day_rows.extend(fixed_rows)

		if rng.random() < args.income_rate or current.day in (1, 15):
			income_rows = generate_income_rows(rng, tx_id, current)
			tx_id += len(income_rows)
			day_rows.extend(income_rows)

		generated = generate_daily_rows(rng, current, tx_id, args.daily_max, args.extreme_rate)
		tx_id += len(generated)
		day_rows.extend(generated)

		for row in day_rows:
			maybe_make_missing(rng, row, args.missing_rate)
			rows.append(row)

			category = row[3].strip() or MISSING_CATEGORY_LABEL
			if category == INCOME_CATEGORY:
				continue
			amount_text = row[2].replace("$", "").replace(",", "").strip()
			if amount_text and amount_text != "-":
				try:
					amount = abs(float(amount_text))
				except ValueError:
					continue
				month_key = current.strftime("%Y-%m")
				month_totals[month_key] = month_totals.get(month_key, 0.0) + amount

	monthly_summary_columns(rows, month_totals)
	return rows


def write_csv(path: Path, rows: List[list[str]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.writer(handle)
		writer.writerow(HEADER)
		writer.writerows(rows)


def main() -> None:
	args = parse_args()
	rows = generate_rows(args)
	write_csv(args.output, rows)
	print(f"Wrote {len(rows)} rows to {args.output}")
	print(
		"Config:",
		f"seed={args.seed}",
		f"months={args.months}",
		f"missing_rate={args.missing_rate}",
		f"extreme_rate={args.extreme_rate}",
	)


if __name__ == "__main__":
	main()
