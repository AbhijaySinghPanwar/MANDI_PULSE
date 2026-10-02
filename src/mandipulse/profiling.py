"""Phase 0 profiling of the Kaggle archive.

The archive has ~76M rows, so it is never loaded into pandas. DuckDB queries the
Parquet files in place; only small aggregated results come back into memory.

Each query lives in analysis/queries/phase0/*.sql and reads from three views
defined here:
  prices        - every row of the archive, with consistent column types
  scope_prices  - prices filtered to the commodities and states in settings.yaml
  source_files  - the raw files on disk (name, format, size in bytes)
Results are written to reports/tables/phase0/<query name>.csv.
"""

import duckdb

from mandipulse.config import PROJECT_ROOT, get_settings

QUERY_DIR = PROJECT_ROOT / "analysis" / "queries" / "phase0"
OUT_DIR = PROJECT_ROOT / "reports" / "tables" / "phase0"
SLOW_QUERIES = {"99_csv_parquet_parity"}


def _sql_list(values: list[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def connect() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with the profiling views registered."""
    cfg = get_settings()
    kaggle = cfg["sources"]["kaggle"]
    parquet_glob = (PROJECT_ROOT / kaggle["parquet_glob"]).as_posix()
    csv_glob = (PROJECT_ROOT / kaggle["csv_glob"]).as_posix()
    commodities = _sql_list(cfg["scope"]["commodities"])
    states = _sql_list(cfg["scope"]["states"])

    con = duckdb.connect()
    # Older files store prices as INT64 and newer ones as DOUBLE, so cast explicitly.
    con.sql(f"""
        create view prices as
        select
            State as state, District as district, Market as market,
            Commodity as commodity, Variety as variety, Grade as grade,
            Arrival_Date as arrival_date_raw,
            try_cast(Arrival_Date as date) as arrival_date,
            cast(Min_Price as double) as min_price,
            cast(Max_Price as double) as max_price,
            cast(Modal_Price as double) as modal_price,
            Commodity_Code as commodity_code,
            cast(regexp_extract(filename, '(\\d{{4}})\\.parquet$', 1) as integer) as file_year
        from read_parquet('{parquet_glob}', filename = true, union_by_name = true)
    """)
    con.sql(f"""
        create view scope_prices as
        select * from prices
        where commodity in ({commodities}) and state in ({states})
    """)
    con.sql(f"""
        create view source_files as
        select regexp_extract(filename, '[^/\\\\]+$') as file_name, 'parquet' as format, size
        from read_blob('{parquet_glob}')
        union all
        select regexp_extract(filename, '[^/\\\\]+$'), 'csv', size
        from read_blob('{csv_glob}')
    """)
    con.sql(f"create view csv_prices as select * from read_csv('{csv_glob}', all_varchar = true)")
    return con


def run_profile(check_csv: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    for path in sorted(QUERY_DIR.glob("*.sql")):
        name = path.stem
        if name in SLOW_QUERIES and not check_csv:
            print(f"skip  {name} (pass --check-csv to run)")
            continue
        result = con.sql(path.read_text(encoding="utf-8"))
        out = OUT_DIR / f"{name}.csv"
        result.write_csv(str(out))
        print(f"wrote {out.relative_to(PROJECT_ROOT).as_posix()}")
