"""Shared helpers for the Mandi Pulse app: cached data access, banner, labels.

All data comes from mandipulse.serving (marts / ml schemas only), via Postgres or the exported
Parquet files depending on DATA_BACKEND (postgres | parquet).
"""

import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # allow `streamlit run app/Home.py` without installing
    sys.path.insert(0, str(ROOT / "src"))

from mandipulse import serving  # noqa: E402
from mandipulse.config import get_settings  # noqa: E402

COMMODITIES = ["Tomato", "Onion", "Potato"]
UNIT = "₹ per quintal (100 kg)"
CROP_COLORS = {"Tomato": "#2a78d6", "Onion": "#eb6834", "Potato": "#1baf7a"}


@st.cache_data(ttl=3600, show_spinner=False)
def load(name: str) -> pd.DataFrame:
    return serving.load(name)


@st.cache_data(ttl=3600, show_spinner=False)
def read_json(relative: str) -> dict:
    return serving.read_json(relative)


@st.cache_data(ttl=3600, show_spinner=False)
def read_csv(relative: str) -> pd.DataFrame:
    return serving.read_csv(relative)


def settings() -> dict:
    return get_settings()


def data_as_of() -> pd.Timestamp:
    return pd.Timestamp(load("meta")["data_as_of"].iloc[0])


def page_setup(title: str, icon: str = "🧅") -> None:
    st.set_page_config(page_title=f"{title} · Mandi Pulse", page_icon=icon, layout="wide")
    st.title(title)
    banner()


def banner() -> None:
    as_of = data_as_of()
    st.info(
        f"**Data as of {as_of:%d %b %Y}**: the latest date in the cleaned source archive "
        "(Kaggle / Agmarknet). Newer archive data from after the Nov-2025 source change is not "
        f"used yet. All prices are wholesale modal prices in {UNIT}.",
        icon="📅",
    )


def market_options(markets: pd.DataFrame) -> dict[str, str]:
    """market_key -> 'State › District › Market' (sorted, so the list reads grouped)."""
    m = markets.sort_values(["state", "district", "market"])
    return dict(
        zip(m["market_key"], m["state"] + " › " + m["district"] + " › " + m["market"], strict=True)
    )


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


VERIFY_BADGE = "⚠️ Verify before acting"
VERIFY_NOTE = (
    "⚠️ **Verify before acting** = the latest report is more than 3× away from the same-day median "
    "of the state's markets, or it is a single low report not yet confirmed by a second one. "
    "Call the mandi or check the next report before you act on it."
)


def verify_label(reason) -> str:
    """Badge text for the 'Check' column: empty when the latest report looks consistent."""
    return f"{VERIFY_BADGE}: {reason}" if isinstance(reason, str) and reason else ""


def rupees(x) -> str:
    return "–" if pd.isna(x) else f"₹{x:,.0f}"
