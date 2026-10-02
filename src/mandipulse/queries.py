"""Run every saved query in analysis/queries/<folder>/ against Postgres and save each result
to reports/tables/<folder>/<query>.csv (spec 8: every reported number comes from a saved query).

    python -m mandipulse queries phase2
"""

from pathlib import Path

import pandas as pd

from mandipulse.config import PROJECT_ROOT
from mandipulse.db import get_engine

QUERY_ROOT = PROJECT_ROOT / "analysis" / "queries"
TABLE_ROOT = PROJECT_ROOT / "reports" / "tables"


def run_folder(folder: str) -> list[Path]:
    engine = get_engine()
    out_dir = TABLE_ROOT / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sql_file in sorted((QUERY_ROOT / folder).glob("*.sql")):
        df = pd.read_sql(sql_file.read_text(encoding="utf-8"), engine)  # aggregates only
        out = out_dir / f"{sql_file.stem}.csv"
        df.to_csv(out, index=False)
        written.append(out)
    return written
