"""Load the ML inputs from Postgres (small, already-aggregated tables; never the raw archive).

Prices: marts.int_analysis_prices = fact_daily_price restricted to the main period, valid rows,
markets with data, suspect-low rows excluded (one REAL report per market x commodity x day).
"""

import pandas as pd

from mandipulse.queries import run_sql

PRICES_SQL = """
select market_key, commodity_key, commodity, state, date, modal_price::float8 as price
from marts.int_analysis_prices
order by market_key, commodity_key, date
"""

CRASH_SQL = """
select market_key, commodity_key, date, is_crash, lookback_median::float8 as lookback_median
from marts.int_crash_labels
where is_crash is not null
"""


def load_prices() -> pd.DataFrame:
    df = run_sql(PRICES_SQL)
    df["date"] = pd.to_datetime(df["date"])
    df["commodity_key"] = df["commodity_key"].astype(int)
    return df


def load_crash_labels() -> pd.DataFrame:
    df = run_sql(CRASH_SQL)
    df["date"] = pd.to_datetime(df["date"])
    df["commodity_key"] = df["commodity_key"].astype(int)
    df["is_crash"] = df["is_crash"].astype(int)
    return df
