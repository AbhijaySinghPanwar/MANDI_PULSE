"""Kaggle load: scope filter, period tagging, rejects, and idempotency.

Uses a tiny synthetic Parquet archive and a throwaway Postgres schema. Skipped when
Postgres (DATABASE_URL) is not reachable.
"""

import uuid

import duckdb
import pytest
from sqlalchemy import text

from mandipulse.ingest.load import load_kaggle

COLS = (
    "State, District, Market, Commodity, Variety, Grade, Arrival_Date, "
    "Min_Price, Max_Price, Modal_Price, Commodity_Code"
)

# fmt: off
ROWS_2024 = [  # prices stored as BIGINT in this file (type drift, like 2001.parquet)
    ("Maharashtra", "Nashik", "Lasalgaon", "Onion", "Red", "FAQ", "2024-01-05", 1000, 1400, 1200, 23),
    ("Maharashtra", "Nashik", "Lasalgaon", "Onion", "Red", "FAQ", "2024-01-05", 1000, 1400, 1200, 23),  # exact dup: kept in raw
    ("Maharashtra", "Nashik", "Lasalgaon", "Onion Green", "Other", "FAQ", "2024-01-05", 900, 1100, 1000, 358),
    ("Gujarat", "Anand", "Anand", "Sweet Potato", "Other", "FAQ", "2024-01-05", 900, 1100, 1000, 152),
    ("Karnataka", "Kolar", "Kolar", "Tomato", "Local", "FAQ", "2024-01-05", 500, 900, 700, 78),
    ("Maharashtra", "Nashik", "Lasalgaon", "Onion", "Red", "FAQ", "2017-12-31", 800, 1000, 900, 23),
    ("Madhya Pradesh", "Indore", "Indore (F&V)", "Potato", "Local", "FAQ", "2024-03-01", 800, 1000, None, 24),  # rejected
]
ROWS_2025 = [  # prices stored as DOUBLE
    ("Uttar Pradesh", "Agra", "Agra", "Tomato", "Local", "FAQ", "2025-10-31", 1500.0, 1900.0, 1700.0, 78),
    ("Uttar Pradesh", "Agra", "Agra APMC", "Tomato", "Local", "FAQ", "2025-11-01", 1600.0, 2000.0, 1800.0, 78),
]
# fmt: on


def write_parquet(path, rows, price_type):
    con = duckdb.connect()
    con.sql(f"""create table t (State varchar, District varchar, Market varchar,
        Commodity varchar, Variety varchar, Grade varchar, Arrival_Date varchar,
        Min_Price {price_type}, Max_Price {price_type}, Modal_Price {price_type},
        Commodity_Code bigint)""")
    con.executemany(f"insert into t ({COLS}) values (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.sql(f"copy t to '{path.as_posix()}' (format parquet)")


@pytest.fixture
def engine():
    from mandipulse.db import get_engine

    try:
        eng = get_engine()
        with eng.connect() as c:
            c.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")
    return eng


@pytest.fixture
def schema(engine):
    name = f"test_raw_{uuid.uuid4().hex[:8]}"
    yield name
    with engine.begin() as c:
        c.execute(text(f"drop schema if exists {name} cascade"))


@pytest.fixture
def archive(tmp_path):
    write_parquet(tmp_path / "2024.parquet", ROWS_2024, "bigint")
    write_parquet(tmp_path / "2025.parquet", ROWS_2025, "double")
    return (tmp_path / "*.parquet").as_posix()


def count(engine, sql):
    with engine.connect() as c:
        return c.execute(text(sql)).all()


def test_scope_filter_periods_and_rejects(engine, schema, archive):
    stats = load_kaggle(engine, schema=schema, parquet_glob=archive)
    assert stats["rows_fetched"] == 5  # 2 Onion (incl. dup) + 1 MP Potato + 2 UP Tomato
    assert stats["rows_rejected"] == 1  # MP potato with null modal price
    assert stats["rows_loaded"] == 4
    rows = count(
        engine,
        f"select commodity, state, period, count(*) from {schema}.mandi_prices "
        "group by 1, 2, 3 order by 1, 2, 3",
    )
    assert rows == [
        ("Onion", "Maharashtra", "main", 2),
        ("Tomato", "Uttar Pradesh", "main", 1),
        ("Tomato", "Uttar Pradesh", "post_format_change", 1),
    ]
    excluded = count(
        engine,
        f"select count(*) from {schema}.mandi_prices "
        "where commodity in ('Onion Green', 'Sweet Potato') "
        "or state = 'Karnataka' or arrival_date < '2018-01-01'",
    )
    assert excluded == [(0,)]
    lineage = count(
        engine, f"select distinct source, source_file from {schema}.mandi_prices order by 2"
    )
    assert lineage == [("kaggle_archive", "2024.parquet"), ("kaggle_archive", "2025.parquet")]


def test_rerun_replaces_instead_of_duplicating(engine, schema, archive):
    first = load_kaggle(engine, schema=schema, parquet_glob=archive)
    second = load_kaggle(engine, schema=schema, parquet_glob=archive)
    assert second["rows_replaced"] == first["rows_loaded"]
    total = count(engine, f"select count(*), count(distinct run_id) from {schema}.mandi_prices")
    assert total == [(4, 1)]  # same rows, all from the latest run
    log = count(engine, f"select status, rows_loaded from {schema}.ingest_log order by started_at")
    assert log == [("success", 4), ("success", 4)]


def test_failed_run_is_logged_and_keeps_previous_rows(engine, schema, archive, tmp_path):
    load_kaggle(engine, schema=schema, parquet_glob=archive)
    with pytest.raises(duckdb.Error):
        load_kaggle(engine, schema=schema, parquet_glob=(tmp_path / "missing*.parquet").as_posix())
    assert count(engine, f"select count(*) from {schema}.mandi_prices") == [(4,)]
    statuses = count(engine, f"select status from {schema}.ingest_log order by started_at")
    assert statuses == [("success",), ("failed",)]
