"""The Postgres and Parquet backends of the app's data layer must return identical tables."""

import pandas as pd
import pytest

from mandipulse.serving import APP_EXPORT_DIR, DATASETS, load


def postgres_available() -> bool:
    try:
        load("meta", "postgres")
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not (postgres_available() and (APP_EXPORT_DIR / "meta.parquet").exists()),
    reason="needs Postgres AND exports/app (run `python -m mandipulse export`)",
)


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_backends_return_identical_tables(name):
    pg = load(name, "postgres")
    pq = load(name, "parquet")
    assert list(pg.columns) == list(pq.columns)
    assert len(pg) == len(pq)
    pd.testing.assert_frame_equal(pg, pq, check_dtype=False, check_exact=False, rtol=1e-9)


def test_unknown_backend_is_rejected(monkeypatch):
    from mandipulse.serving import backend

    monkeypatch.setenv("DATA_BACKEND", "excel")
    with pytest.raises(ValueError):
        backend()
