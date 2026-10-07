"""Run every saved query in analysis/queries/<folder>/ against Postgres and save each result
to reports/tables/<folder>/<query>.csv (spec 8: every reported number comes from a saved query).

    python -m mandipulse queries phase2
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd

from mandipulse.config import PROJECT_ROOT
from mandipulse.db import get_engine

QUERY_ROOT = PROJECT_ROOT / "analysis" / "queries"
TABLE_ROOT = PROJECT_ROOT / "reports" / "tables"


def run_sql(sql: str) -> pd.DataFrame:
    """Run one saved query (no parameters, so '%' in labels is safe) -> small DataFrame."""
    raw = get_engine().raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(sql)
        cols = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        raw.close()
    # Postgres numeric arrives as Decimal; plain floats are easier to plot and compare.
    for col in df.columns:
        values = df[col].dropna()
        if len(values) and all(isinstance(v, Decimal) for v in values):
            df[col] = df[col].astype(float)
    return df


def run_folder(folder: str, only: str | None = None) -> list[Path]:
    """Run analysis/queries/<folder>/*.sql and save each result as CSV."""
    out_dir = TABLE_ROOT / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sql_file in sorted((QUERY_ROOT / folder).glob(f"{only or '*'}.sql")):
        df = run_sql(sql_file.read_text(encoding="utf-8"))  # aggregates only
        out = out_dir / f"{sql_file.stem}.csv"
        df.to_csv(out, index=False)
        written.append(out)
    return written
