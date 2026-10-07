"""The committed app snapshot (data/app_snapshot/) is complete and readable without a database."""

import pandas as pd
import pytest

from mandipulse.serving import DATASETS, SNAPSHOT_DIR


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_snapshot_has_every_dataset(name):
    df = pd.read_parquet(SNAPSHOT_DIR / f"{name}.parquet")
    assert len(df.columns) > 0


def test_snapshot_is_small_enough_to_commit():
    total = sum((SNAPSHOT_DIR / f"{n}.parquet").stat().st_size for n in DATASETS)
    assert total < 10e6, f"snapshot is {total / 1e6:.1f} MB"


def test_backend_defaults_to_snapshot_without_a_database(monkeypatch):
    from mandipulse import serving

    monkeypatch.delenv("DATA_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert serving.backend() == "parquet"
