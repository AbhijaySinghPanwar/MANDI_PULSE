"""Smoke tests: every app page renders without an exception, with each available backend."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mandipulse.serving import APP_EXPORT_DIR, load

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = [APP / "Home.py", *sorted((APP / "pages").glob("*.py"))]


def available_backends() -> list[str]:
    found = []
    try:
        load("meta", "postgres")
        found.append("postgres")
    except Exception:  # noqa: BLE001
        pass
    if (APP_EXPORT_DIR / "meta.parquet").exists():
        found.append("parquet")
    return found


BACKENDS = available_backends()


@pytest.mark.skipif(not BACKENDS, reason="no data backend (Postgres or exports/app) available")
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_renders(page, backend, monkeypatch):
    import streamlit as st

    monkeypatch.setenv("DATA_BACKEND", backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.info, "every page shows the data-as-of banner"
