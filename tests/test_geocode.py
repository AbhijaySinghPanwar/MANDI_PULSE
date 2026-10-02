"""Geocoding logic with a fake geocoder (no network)."""

import pandas as pd
import pytest

from mandipulse.geo.geocode import Hit, geocode_markets, market_names

PLACES = {  # query prefix -> (lat, lon, state)
    "Pune district": (18.52, 73.86, "Maharashtra"),
    "Nashik district": (20.00, 73.79, "Maharashtra"),
    "Pimpri, Pune": (18.63, 73.80, "Maharashtra"),
    "Niphad, Nashik": (20.08, 74.11, "Maharashtra"),
    "Manmad, Nashik": (26.0, 80.0, "Uttar Pradesh"),  # same-named place, wrong state
    "Kalvan, Nashik": (22.0, 78.0, "Maharashtra"),  # right state, but >100 km away
}


class FakeGeocoder:
    def __init__(self, fail_after: int | None = None):
        self.calls: list[str] = []
        self.fail_after = fail_after

    def __call__(self, query: str) -> Hit | None:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise ConnectionError("simulated crash")
        self.calls.append(query)
        for prefix, (lat, lon, state) in PLACES.items():
            if query.startswith(prefix + ","):
                return Hit(lat, lon, state, prefix)
        return None


MARKETS = [
    ("Maharashtra", "Pune", "Pune (Pimpri)"),
    ("Maharashtra", "Nashik", "Lasalgaon (Niphad)"),
    ("Maharashtra", "Nashik", "Manmad"),
    ("Maharashtra", "Nashik", "Kalvan"),
]


def run(tmp_path, geocoder, **kw):
    return geocode_markets(
        MARKETS,
        geocoder,
        tmp_path / "m.csv",
        tmp_path / "d.csv",
        max_km=100,
        progress=lambda _: None,
        **kw,
    )


def test_market_names():
    assert market_names("Pune (Pimpri)") == ["Pimpri", "Pune"]
    assert market_names("Damoh (F&V)") == ["Damoh"]
    assert market_names("Anand (Veg,Yard,Anand)") == ["Anand"]
    assert market_names("Kalyan") == ["Kalyan"]


def test_precision_and_validation(tmp_path):
    run(tmp_path, FakeGeocoder())
    geo = pd.read_csv(tmp_path / "m.csv").set_index("market")
    assert geo.loc["Pune (Pimpri)", "geo_precision"] == "market"
    assert geo.loc["Lasalgaon (Niphad)", "geo_precision"] == "market"
    # Wrong-state and too-far hits are rejected and fall back to the district centroid.
    assert geo.loc["Manmad", "geo_precision"] == "district_centroid"
    assert geo.loc["Kalvan", "geo_precision"] == "district_centroid"
    assert geo.loc["Kalvan", "latitude"] == pytest.approx(20.00)


def test_resumes_from_cache_after_a_crash(tmp_path):
    with pytest.raises(ConnectionError):
        run(tmp_path, FakeGeocoder(fail_after=4))
    partial = pd.read_csv(tmp_path / "m.csv")
    assert 0 < len(partial) < len(MARKETS)

    second = FakeGeocoder()
    run(tmp_path, second)
    final = pd.read_csv(tmp_path / "m.csv")
    assert len(final) == len(MARKETS)  # no duplicates
    assert set(final.market) == {m for _, _, m in MARKETS}
    assert not any(q.startswith(("Pimpri", "Pune district")) for q in second.calls)

    third = FakeGeocoder()
    assert run(tmp_path, third) == 0  # everything cached
    assert third.calls == []
