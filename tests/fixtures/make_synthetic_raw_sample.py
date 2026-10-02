"""Generate tests/fixtures/synthetic_raw_sample.csv: a SYNTHETIC, TEST-ONLY raw price sample.

Market names are real (so the alias and geocode reference seeds resolve), but every price is
made up. CI loads this file instead of the (gitignored) Kaggle archive so that `dbt build`
can run end to end. Never use it for analysis.

    python tests/fixtures/make_synthetic_raw_sample.py

Deterministic (fixed seed). Deliberate edge cases, so the flags and tests have work to do:
  - an exact duplicate row                          -> dropped by staging dedupe
  - min/max = 0 placeholders                        -> treated as missing, row kept
  - an outlier (10x) and a unit error (Rs 20)       -> flagged invalid
  - a series persistently ~4x below the state       -> flag_persistent_low (suspect)
  - a tomato crash in August                        -> crash labels / seasonality
  - 'Lasalgaon APMC' after the Nov-2025 change      -> alias to Lasalgaon, period post_format_change
  - Jangipura filed under district Hapur            -> district correction to Ghazipur
"""

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("synthetic_raw_sample.csv")
COLUMNS = [
    "State",
    "District",
    "Market",
    "Commodity",
    "Variety",
    "Grade",
    "Arrival_Date",
    "Min_Price",
    "Max_Price",
    "Modal_Price",
    "Commodity_Code",
]
CODES = {"Tomato": 78, "Onion": 23, "Potato": 24}
BASE = {"Tomato": 1200, "Onion": 1600, "Potato": 1300}

# (state, district, market, price factor)
MARKETS = [
    ("Maharashtra", "Nashik", "Lasalgaon", 1.00),
    ("Maharashtra", "Nashik", "Pimpalgaon", 1.04),
    ("Maharashtra", "Nashik", "Manmad", 0.95),
    ("Maharashtra", "Nashik", "Nasik", 1.10),
    ("Maharashtra", "Nashik", "Lasalgaon (Niphad)", 0.98),
    ("Maharashtra", "Pune", "Pune", 1.20),
    ("Maharashtra", "Pune", "Khed (Chakan)", 1.12),
]
LOW_SERIES = ("Manmad", "Tomato")  # persistently ~1/4 of the state median


def price(rng: random.Random, crop: str, factor: float, d: date) -> float:
    day = (d - date(2025, 1, 1)).days
    seasonal = 1 + 0.25 * math.sin(2 * math.pi * day / 365)
    crash = 0.45 if crop == "Tomato" and date(2025, 8, 10) <= d <= date(2025, 8, 31) else 1.0
    return round(BASE[crop] * factor * seasonal * crash * rng.uniform(0.93, 1.07))


def row(state, district, market, crop, d, modal, lo=None, hi=None, variety="Other"):
    lo = round(modal * 0.85) if lo is None else lo
    hi = round(modal * 1.15) if hi is None else hi
    return [
        state,
        district,
        market,
        crop,
        variety,
        "FAQ",
        d.isoformat(),
        lo,
        hi,
        modal,
        CODES[crop],
    ]


def main() -> None:
    rng = random.Random(42)
    rows = []
    d = date(2025, 3, 1)
    while d <= date(2025, 10, 31):
        for state, district, market, factor in MARKETS:
            for crop in CODES:
                if rng.random() < 0.15:  # markets don't report every day
                    continue
                f = factor * (0.25 if (market, crop) == LOW_SERIES else 1.0)
                rows.append(row(state, district, market, crop, d, price(rng, crop, f, d)))
        # Ghazipur towns (Uttar Pradesh): one filed under Hapur (district correction)
        if d.day % 2 == 0:
            rows.append(
                row(
                    "Uttar Pradesh", "Hapur", "Jangipura", "Potato", d, price(rng, "Potato", 0.9, d)
                )
            )
        d += timedelta(days=1)

    # Post-format-change rows under the renamed market
    for k in range(10):
        dd = date(2025, 11, 29) + timedelta(days=k)
        rows.append(
            row(
                "Maharashtra", "Nashik", "Lasalgaon APMC", "Onion", dd, price(rng, "Onion", 1.0, dd)
            )
        )

    # Edge cases
    rows.append(list(rows[100]))  # exact duplicate
    rows.append(
        row(
            "Maharashtra",
            "Nashik",
            "Nasik",
            "Onion",
            date(2025, 6, 2),
            1700,
            lo=0,
            hi=0,
            variety="Red",
        )
    )  # 0 min/max
    rows.append(
        row("Maharashtra", "Pune", "Pune", "Potato", date(2025, 7, 15), 15000, variety="Jyoti")
    )  # outlier
    rows.append(
        row(
            "Maharashtra",
            "Nashik",
            "Pimpalgaon",
            "Onion",
            date(2025, 7, 16),
            20,
            lo=15,
            hi=25,
            variety="Red",
        )
    )  # unit error

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"wrote {OUT.name}: {len(rows)} synthetic rows")


if __name__ == "__main__":
    main()
