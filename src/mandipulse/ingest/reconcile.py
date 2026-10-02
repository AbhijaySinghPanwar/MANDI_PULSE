"""Compare row counts in Postgres raw.mandi_prices with the Phase 0 DuckDB profile.

Writes reports/tables/phase1/load_reconciliation.csv (commodity x state x year) with both
counts and their difference. A non-zero difference must be explained in PROGRESS.md.
"""

import duckdb
import pandas as pd

from mandipulse.config import PROJECT_ROOT, get_settings
from mandipulse.db import get_engine

QUERY = PROJECT_ROOT / "analysis" / "queries" / "phase1" / "raw_rows_by_year.sql"
PROFILE = PROJECT_ROOT / "reports" / "tables" / "phase0" / "07_scope_rows_by_year.csv"
OUT = PROJECT_ROOT / "reports" / "tables" / "phase1" / "load_reconciliation.csv"


def reconcile() -> pd.DataFrame:
    cfg = get_settings()
    raw = pd.read_sql(QUERY.read_text(encoding="utf-8"), get_engine())  # small: ~100 rows
    duck = duckdb.connect()
    duck.register("raw_counts", raw)
    states = ", ".join(f"'{s}'" for s in cfg["scope"]["states"])
    result = duck.sql(f"""
        with profile as (
            select commodity, state, year, n_rows as n_rows_profile
            from read_csv('{PROFILE.as_posix()}')
            where state in ({states}) and year >= year(date '{cfg["scope"]["backfill_start"]}')
        )
        select commodity, state, year,
               coalesce(p.n_rows_profile, 0) as n_rows_profile,
               coalesce(r.n_rows_raw, 0)     as n_rows_raw,
               coalesce(r.n_rows_raw, 0) - coalesce(p.n_rows_profile, 0) as diff
        from profile p full outer join raw_counts r using (commodity, state, year)
        order by commodity, state, year
    """).df()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    return result
