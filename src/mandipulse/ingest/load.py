"""Load the in-scope slice of the Kaggle archive into Postgres raw.mandi_prices.

DuckDB filters the Parquet archive in place (it is never loaded into pandas) and writes the
slice to a temporary CSV, which Postgres ingests with COPY.

Idempotency: each run deletes every existing row with the same `source` and inserts the
fresh slice in ONE transaction, so re-running replaces rather than duplicates. The archive
is static, so a full replace of the source is simpler and safer than date-level upserts.
Each run is recorded in raw.ingest_log.
"""

import re
import tempfile
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
from sqlalchemy import Engine, text

from mandipulse.config import PROJECT_ROOT, get_settings

SCHEMA_SQL = Path(__file__).with_name("schema.sql")

# Column order shared by the DuckDB export and the Postgres COPY.
COLUMNS = [
    "state",
    "district",
    "market",
    "commodity",
    "variety",
    "grade",
    "arrival_date",
    "min_price",
    "max_price",
    "modal_price",
    "commodity_code",
    "source",
    "source_file",
    "period",
    "ingested_at",
    "run_id",
]


def _sql_list(values: list[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _check_identifier(name: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
        raise ValueError(f"Unsafe schema name: {name!r}")
    return name


def init_raw_schema(engine: Engine, schema: str = "raw") -> None:
    """Create the raw schema and tables if missing."""
    ddl = SCHEMA_SQL.read_text(encoding="utf-8").format(schema=_check_identifier(schema))
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def _reader(glob: str) -> str:
    """DuckDB table function for the archive: Parquet (the Kaggle archive) or CSV in the same
    column layout (the synthetic CI fixture in tests/fixtures/)."""
    if glob.lower().endswith(".csv"):
        return f"read_csv('{glob}', header = true, filename = true, union_by_name = true)"
    return f"read_parquet('{glob}', filename = true, union_by_name = true)"


def scope_select_sql(parquet_glob: str, cfg: dict) -> str:
    """DuckDB SELECT over the archive: in-scope rows with a `valid` flag and a `period` tag."""
    scope, periods = cfg["scope"], cfg["periods"]
    commodities = scope["commodities"]
    excluded = scope["exclude_commodities"]
    overlap = set(commodities) & set(excluded)
    if overlap:
        raise ValueError(f"Commodities both in scope and excluded: {overlap}")
    main_end = periods["main"]["end"]
    post_start = periods["post_format_change"]["start"]
    if date.fromisoformat(post_start) - date.fromisoformat(main_end) != timedelta(days=1):
        raise ValueError("periods.main.end and periods.post_format_change.start must be contiguous")

    return f"""
        with src as (
            select
                State as state, District as district, Market as market,
                Commodity as commodity, Variety as variety, Grade as grade,
                try_cast(Arrival_Date as date) as arrival_date,
                cast(Min_Price as double) as min_price,
                cast(Max_Price as double) as max_price,
                cast(Modal_Price as double) as modal_price,
                Commodity_Code as commodity_code,
                regexp_extract(filename, '[^/\\\\]+$') as source_file
            from {_reader(parquet_glob)}
            where Commodity in ({_sql_list(commodities)})
              and Commodity not in ({_sql_list(excluded)})
              and State in ({_sql_list(scope["states"])})
        )
        select *,
            (arrival_date is not null
             and coalesce(trim(state), '') <> '' and coalesce(trim(district), '') <> ''
             and coalesce(trim(market), '') <> '' and modal_price is not null) as valid,
            case when arrival_date <= date '{main_end}' then 'main'
                 when arrival_date >= date '{post_start}' then 'post_format_change'
            end as period
        from src
        where arrival_date is null or arrival_date >= date '{scope["backfill_start"]}'
    """


def load_kaggle(
    engine: Engine,
    schema: str = "raw",
    parquet_glob: str | None = None,
    cfg: dict | None = None,
) -> dict:
    """Replace all `kaggle_archive` rows in {schema}.mandi_prices with a fresh scope slice."""
    cfg = cfg or get_settings()
    schema = _check_identifier(schema)
    kaggle = cfg["sources"]["kaggle"]
    source = kaggle["source_tag"]
    parquet_glob = parquet_glob or (PROJECT_ROOT / kaggle["parquet_glob"]).as_posix()

    init_raw_schema(engine, schema)
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"insert into {schema}.ingest_log (run_id, source, started_at, status) "
                "values (:r, :s, :t, 'running')"
            ),
            {"r": run_id, "s": source, "t": started_at},
        )

    stats = {"run_id": run_id, "source": source}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "slice.csv"
            duck = duckdb.connect()
            duck.sql(f"create view slice as {scope_select_sql(parquet_glob, cfg)}")
            fetched, rejected = duck.sql(
                "select count(*), count(*) filter (where not valid) from slice"
            ).fetchone()
            extra = {"source": source, "ingested_at": started_at.isoformat(), "run_id": run_id}
            select_cols = ", ".join(f"'{extra[c]}' as {c}" if c in extra else c for c in COLUMNS)
            duck.sql(
                f"copy (select {select_cols} from slice where valid) "
                f"to '{csv_path.as_posix()}' (header, delimiter ',')"
            )
            duck.close()

            with engine.begin() as conn:
                replaced = conn.execute(
                    text(f"delete from {schema}.mandi_prices where source = :s"), {"s": source}
                ).rowcount
                cursor = conn.connection.driver_connection.cursor()
                copy_sql = (
                    f"copy {schema}.mandi_prices ({', '.join(COLUMNS)}) "
                    "from stdin with (format csv, header true)"
                )
                with cursor.copy(copy_sql) as copy, open(csv_path, "rb") as f:
                    while chunk := f.read(1 << 20):
                        copy.write(chunk)
                loaded = conn.execute(
                    text(f"select count(*) from {schema}.mandi_prices where run_id = :r"),
                    {"r": run_id},
                ).scalar_one()

        stats.update(
            rows_fetched=fetched, rows_rejected=rejected, rows_loaded=loaded, rows_replaced=replaced
        )
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"update {schema}.ingest_log set finished_at = :f, rows_fetched = :fe, "
                    "rows_rejected = :rj, rows_loaded = :lo, rows_replaced = :rp, "
                    "status = 'success' where run_id = :r"
                ),
                {
                    "f": datetime.now(UTC),
                    "fe": fetched,
                    "rj": rejected,
                    "lo": loaded,
                    "rp": replaced,
                    "r": run_id,
                },
            )
        return stats
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"update {schema}.ingest_log set finished_at = :f, status = 'failed', "
                    "error = :e where run_id = :r"
                ),
                {"f": datetime.now(UTC), "e": f"{type(exc).__name__}: {exc}"[:2000], "r": run_id},
            )
        raise
