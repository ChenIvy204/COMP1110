"""Generate realistic worker-style finance test data.

Running python test_data_generator.py asks for:
1. months to generate
2. extreme-case probability
3. random seed
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


HEADER = ["transaction_id", "date", "amount in HKD", "type", "category", "description"]
DEFAULT_OUTPUT = Path("generated_worker_spending.csv")
DEFAULT_START = "2026-01-01"
DEFAULT_MONTHS = 5
DEFAULT_EXTREME_RATE = 0.035
DEFAULT_SEED = 42
INCOME_CATEGORY = "Income"
EXPENSE_TYPE = "expense"
INCOME_TYPE = "income"


@dataclass(frozen=True)
class CategoryProfile:
	category: str
	weight: float
	weekday_range: tuple[float, float]
	weekend_range: tuple[float, float]
	descriptions: tuple[str, ...]


@dataclass(frozen=True)
class GeneratorSettings:
	months: int
	extreme_rate: float
	seed: int

# standardize office spending patterns
CATEGORY_PROFILES: tuple[CategoryProfile, ...] = (
	CategoryProfile("Meals", 0.48, (35, 130), (55, 360), ("Breakfast", "Lunch", "Cafe", "Snack and drink", "Dinner")),
	CategoryProfile("Transport", 0.22, (18, 45), (35, 110), ("MTR", "Taxi", "Bus", "Railway")),
	CategoryProfile("Shopping", 0.12, (25, 160), (90, 620), ("Supermarket shopping", "Household supplies", "Clothes and toiletries", "Seasonal shopping")),
	CategoryProfile("Accommodation", 0.06, (6400, 11000), (6400, 11000), ("Monthly rent", "Short-term accommodation payment")),
	CategoryProfile("Fun", 0.07, (45, 260), (120, 780), ("Cinema", "KTV", "Concert ticket", "Games and hobbies", "Weekend entertainment")),
	CategoryProfile("Other", 0.05, (40, 240), (55, 320), ("Phone and subscription bill", "Office stationery", "Utilities payment", "Unexpected small expense")),
)
DAILY_EXPENSE_PROFILES = tuple(profile for profile in CATEGORY_PROFILES if profile.category != "Accommodation")
PROFILE_WEIGHTS = [profile.weight for profile in DAILY_EXPENSE_PROFILES]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Generate worker-style finance test data")
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path")
	parser.add_argument("--start", default=DEFAULT_START, help="Start date in YYYY-MM-DD")
	return parser.parse_args()

#invalid input handling
def prompt_int_value(label: str, default: int, minimum: int) -> int:
	while True:
		raw_value = input(f"{label} [{default}]: ").strip()
		if not raw_value:
			return default
		try:
			value = int(raw_value)
		except ValueError:
			print("Please enter a whole number.")
			continue
		if value < minimum:
			print(f"Please enter a value greater than or equal to {minimum}.")
			continue
		return value


def prompt_float_value(label: str, default: float, minimum: float, maximum: float) -> float:
	while True:
		raw_value = input(f"{label} [{default}]: ").strip()
		if not raw_value:
			return default
		try:
			value = float(raw_value)
		except ValueError:
			print("Please enter a number.")
			continue
		if value < minimum or value > maximum:
			print(f"Please enter a value between {minimum} and {maximum}.")
			continue
		return value

# collects 3 inputs
def prompt_generation_settings() -> GeneratorSettings:
	print("Interactive generator settings")
	print("Press Enter to keep the current default value.")
	months = prompt_int_value("Months to generate", DEFAULT_MONTHS, minimum=1)
	extreme_rate = prompt_float_value("Extreme-case probability", DEFAULT_EXTREME_RATE, minimum=0.0, maximum=1.0)
	seed = prompt_int_value("Random seed", DEFAULT_SEED, minimum=0)
	return GeneratorSettings(months=months, extreme_rate=extreme_rate, seed=seed)

#date range generator
def daterange(start: date, end: date) -> Iterable[date]:
	current = start
	while current <= end:
		yield current
		current += timedelta(days=1)


def add_months(start: date, months: int) -> date:
	year = start.year + (start.month - 1 + months) // 12
	month = (start.month - 1 + months) % 12 + 1
	return date(year, month, 1)


def format_amount(amount: float) -> str:
	return f"${amount:,.2f}"


def choose_profile(rng: random.Random) -> CategoryProfile:
	return rng.choices(DAILY_EXPENSE_PROFILES, weights=PROFILE_WEIGHTS, k=1)[0]

# turns some normal expenses into large outliers for alert testing
def extreme_cases(rng: random.Random, amount: float, category: str, extreme_rate: float) -> float:
	if rng.random() >= extreme_rate:
		return amount
	if category == "Shopping":
		return round(amount * rng.uniform(3.5, 8.0), 2)
	if category == "Fun":
		return round(amount * rng.uniform(2.5, 7.0), 2)
	return round(amount * rng.uniform(2.0, 5.5), 2)

# injects incomplete rows so import and summary logic sees missing values
def apply_missing_field(rng: random.Random, row: list[str], extreme_rate: float) -> None:
	if rng.random() >= extreme_rate:
		return

	missing_target = rng.choices(
		["amount", "category", "date"],
		weights=[0.4, 0.4, 0.2],
		k=1,
	)[0]

	if missing_target == "amount":
		row[2] = " $-   "
	elif missing_target == "category":
		row[4] = ""
	else:
		row[1] = ""


def build_transaction_row(
	tx_id: int,
	when: date,
	amount: float,
	transaction_type: str,
	category: str,
	description: str,
) -> list[str]:
	return [
		str(tx_id),
		when.strftime("%Y/%-m/%-d"),
		format_amount(amount),
		transaction_type,
		category,
		description,
	]


def weekday_transaction_count(rng: random.Random, current: date) -> int:
	if current.weekday() < 5:
		return rng.randint(3, 5)
	return rng.randint(2, 4)


def generate_income_rows(rng: random.Random, tx_id: int, current: date) -> list[list[str]]:
	rows: list[list[str]] = []
	if current.day in (1, 15) and rng.random() < 0.7:
		amount = round(rng.uniform(14000, 28000), 2)
		description = rng.choice(("Monthly salary", "Allowance from family", "Freelance side income", "Performance bonus"))
		rows.append(build_transaction_row(tx_id, current, amount, INCOME_TYPE, INCOME_CATEGORY, description))
	return rows


def generate_fixed_monthly_rows(rng: random.Random, tx_id: int, current: date) -> list[list[str]]:
	rows: list[list[str]] = []
	if current.day == 5:
		amount = round(rng.uniform(8500, 11000), 2)
		rows.append(build_transaction_row(tx_id, current, amount, EXPENSE_TYPE, "Accommodation", f"Rent ({current.strftime('%B')})"))
	if current.day in (18, 22):
		amount = round(rng.uniform(520, 980), 2)
		rows.append(build_transaction_row(tx_id + len(rows), current, amount, EXPENSE_TYPE, "Other", f"Utilities ({current.strftime('%B')})"))
	return rows

# generates the daily spending records
def generate_daily_rows(rng: random.Random, current: date, next_tx_id: int, extreme_rate: float) -> list[list[str]]:
	rows: list[list[str]] = []
	use_weekend_range = current.weekday() >= 5

	for offset in range(weekday_transaction_count(rng, current)):
		profile = choose_profile(rng)
		amount_range = profile.weekend_range if use_weekend_range else profile.weekday_range
		amount = round(rng.uniform(*amount_range), 2)
		amount = extreme_cases(rng, amount, profile.category, extreme_rate)
		description = rng.choice(profile.descriptions)
		row = build_transaction_row(next_tx_id + offset, current, amount, EXPENSE_TYPE, profile.category, description)
		apply_missing_field(rng, row, extreme_rate)
		rows.append(row)

	return rows


# assembles income, fixed bills, daily spending, and monthly totals into one CSV payload
def generate_rows(start: date, settings: GeneratorSettings) -> list[list[str]]:
	rng = random.Random(settings.seed)
	end = add_months(start, settings.months) - timedelta(days=1)
	rows: list[list[str]] = []
	month_totals: dict[str, float] = {}
	tx_id = 1

	for current in daterange(start, end):
		day_rows = generate_fixed_monthly_rows(rng, tx_id, current)
		tx_id += len(day_rows)

		income_rows = generate_income_rows(rng, tx_id, current)
		tx_id += len(income_rows)
		day_rows.extend(income_rows)

		daily_rows = generate_daily_rows(rng, current, tx_id, settings.extreme_rate)
		tx_id += len(daily_rows)
		day_rows.extend(daily_rows)

		for row in day_rows:
			rows.append(row)
			if row[3] == INCOME_TYPE:
				continue
			month_key = current.strftime("%Y-%m")
			amount_text = row[2].replace("$", "").replace(",", "").strip()
			if not amount_text or amount_text == "-":
				continue
			amount = float(amount_text)
			month_totals[month_key] = month_totals.get(month_key, 0.0) + amount
	return rows


def write_csv(path: Path, rows: list[list[str]]) -> None:
	with path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.writer(handle)
		writer.writerow(HEADER)
		writer.writerows(rows)

# keeps old generated files by choosing the next available filename
def unique_output_path(path: Path) -> Path:
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists():
		return path
	for index in range(1, 10_000):
		candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
		if not candidate.exists():
			return candidate
	raise RuntimeError(f"Could not find an available output filename for {path}")

# connects input, generation, and CSV export into one runnable flow
def main() -> None:
	args = parse_args()
	settings = prompt_generation_settings()
	rows = generate_rows(date.fromisoformat(args.start), settings)
	output_path = unique_output_path(args.output)
	write_csv(output_path, rows)
	print(f"Wrote {len(rows)} rows to {output_path}")
	print(f"Config: seed={settings.seed} months={settings.months} extreme_rate={settings.extreme_rate}")


if __name__ == "__main__":
	main()
