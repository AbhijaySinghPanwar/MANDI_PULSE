"""Geocode canonical markets with OpenStreetMap Nominatim (spec 6.4).

- One request per second; contact email NOMINATIM_EMAIL from .env sent as the email= parameter.
- Resumable: every result is appended to the cache CSV as soon as it is known, and markets
  already in the cache are skipped, so an interrupted run continues where it stopped.
- Order of attempts per market:
    1. the place in brackets, if it looks like a locality ('Pune (Pimpri)' -> 'Pimpri')
    2. the name before the brackets ('Damoh (F&V)' -> 'Damoh')
    3. fallback: the district centroid (geo_precision = 'district_centroid')
  A hit only counts if Nominatim puts it in the right state and within
  geo.max_km_from_district of the district centroid; this rejects same-named places elsewhere.
- data/reference/market_geo_overrides.csv wins over everything (geo_precision = 'manual').
"""

import csv
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from mandipulse.config import PROJECT_ROOT, get_settings
from mandipulse.geo.distance import haversine_km

REF = PROJECT_ROOT / "data" / "reference"
MARKET_CACHE = REF / "market_geo.csv"
DISTRICT_CACHE = REF / "district_geo.csv"
OVERRIDES = REF / "market_geo_overrides.csv"
ALIASES = REF / "market_aliases.csv"
DISTRICT_OSM_NAMES = REF / "district_osm_names.csv"  # hand-curated: our spelling -> OSM name

MARKET_FIELDS = [
    "state",
    "district",
    "market",
    "latitude",
    "longitude",
    "geo_precision",
    "query_used",
    "matched_name",
    "km_from_district",
    "geocoded_at",
]
DISTRICT_FIELDS = [
    "state",
    "district",
    "latitude",
    "longitude",
    "query_used",
    "matched_name",
    "geocoded_at",
]
OVERRIDE_FIELDS = ["state", "district", "market", "latitude", "longitude", "note"]

# Bracketed text that describes the yard rather than naming a place.
_DESCRIPTOR = re.compile(
    r"f&v|veg|yard|market|grain|mandi|sub|station|road|dist|frui|bhajipura|phale|co\.?\s*ltd"
    r"|^ex-",  # '(ex-Hapur)' marks a district-corrected record, not a locality
    re.IGNORECASE,
)


@dataclass
class Hit:
    """One Nominatim result."""

    latitude: float
    longitude: float
    state: str  # state according to Nominatim's address details
    display_name: str


# A geocoder takes a free-text query and returns a Hit or None. The real one wraps Nominatim;
# tests pass a fake.
Geocoder = Callable[[str], Hit | None]


class NominatimBlocked(RuntimeError):
    """HTTP 403 from Nominatim: stop instead of retrying (usage-policy block)."""


def nominatim_geocoder(min_delay_s: float = 1.0) -> Geocoder:
    """Nominatim /search client: at most one request per `min_delay_s`, contact email sent in
    the documented `email` parameter. (A User-Agent containing the email was refused with
    HTTP 403 on 2026-10-02, while a plain application User-Agent was accepted.)"""
    email = os.environ.get("NOMINATIM_EMAIL", "").strip()
    if not email:
        raise RuntimeError("NOMINATIM_EMAIL is not set in .env (Nominatim requires a contact).")
    geo_cfg = get_settings()["geo"]
    session = requests.Session()
    session.headers["User-Agent"] = geo_cfg["nominatim_user_agent"]
    last_call = [0.0]

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, _ServerError)),
        wait=wait_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(query: str) -> list[dict]:
        wait = min_delay_s - (time.monotonic() - last_call[0])
        if wait > 0:
            time.sleep(wait)
        last_call[0] = time.monotonic()
        resp = session.get(
            geo_cfg["nominatim_url"],
            timeout=30,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "in",
                "addressdetails": 1,
                "email": email,
            },
        )
        if resp.status_code == 403:
            raise NominatimBlocked(f"HTTP 403 from Nominatim: {resp.text[:200]}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _ServerError(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp.json()

    def geocode(query: str) -> Hit | None:
        results = _get(query)
        if not results:
            return None
        top = results[0]
        return Hit(
            float(top["lat"]),
            float(top["lon"]),
            top.get("address", {}).get("state", ""),
            top.get("display_name", ""),
        )

    return geocode


class _ServerError(RuntimeError):
    pass


def _osm_district_names(path: Path = DISTRICT_OSM_NAMES) -> dict[tuple[str, str], list[str]]:
    if not path.exists():
        return {}
    names: dict[tuple[str, str], list[str]] = {}
    for r in pd.read_csv(path).itertuples():
        names.setdefault((r.state, r.district), []).append(r.osm_name)
    return names


def district_names(district: str, state: str | None = None) -> list[str]:
    """'Vadodara (Baroda)' -> ['Vadodara', 'Baroda']. Curated OSM spellings go first."""
    core = district.split("(")[0].strip()
    alt = [a.strip() for a in re.findall(r"\(([^)]*)\)", district)]
    osm = _osm_district_names().get((state, district), []) if state else []
    return list(dict.fromkeys(n for n in [*osm, core, *alt] if n))


def market_names(market: str) -> list[str]:
    """Place names to try for a canonical market, most specific first."""
    core = market.split("(")[0].strip()
    names = [
        p.strip()
        for p in re.findall(r"\(([^)]*)\)", market)
        if p.strip() and not _DESCRIPTOR.search(p)
    ]
    names.append(core)
    return list(dict.fromkeys(n for n in names if n))


def _same_state(hit: Hit, state: str) -> bool:
    return hit.state.casefold() == state.casefold()


def _read_cache(path: Path, key_fields: list[str]) -> dict[tuple, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {tuple(r[k] for k in key_fields): r for r in csv.DictReader(f)}


def _append(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)


def ensure_overrides_file(path: Path = OVERRIDES) -> None:
    """Create the manual geocode overrides CSV (header only) if it does not exist."""
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(OVERRIDE_FIELDS)


def geocode_district(
    state: str, district: str, geocode: Geocoder, cache: Path, retry_failed: bool = False
) -> dict:
    """Cached district-centre geocode (the fallback location for its markets)."""
    cached = _read_cache(cache, ["state", "district"]).get((state, district))
    if cached and (cached["latitude"] != "" or not retry_failed):
        return cached
    row = {
        "state": state,
        "district": district,
        "latitude": "",
        "longitude": "",
        "query_used": "",
        "matched_name": "",
        "geocoded_at": "",
    }
    for name in district_names(district, state):
        for query in (f"{name} district, {state}, India", f"{name}, {state}, India"):
            hit = geocode(query)
            if hit and _same_state(hit, state):
                row.update(
                    latitude=hit.latitude,
                    longitude=hit.longitude,
                    query_used=query,
                    matched_name=hit.display_name,
                )
                break
        if row["latitude"] != "":
            break
    row["geocoded_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    _append(cache, DISTRICT_FIELDS, row)
    return row


def geocode_market(
    state: str, district: str, market: str, geocode: Geocoder, district_row: dict, max_km: float
) -> dict:
    """Geocode one market; fall back to the district centre if not found or too far from it."""
    row = {
        "state": state,
        "district": district,
        "market": market,
        "latitude": "",
        "longitude": "",
        "geo_precision": "not_found",
        "query_used": "",
        "matched_name": "",
        "km_from_district": "",
    }
    has_centroid = district_row.get("latitude") not in ("", None)
    district_label = district_names(district, state)[0]
    queries = [f"{name}, {district_label}, {state}, India" for name in market_names(market)]
    if has_centroid:  # without the district, a hit is only trusted near the district centroid
        queries += [f"{name}, {state}, India" for name in market_names(market)]
    for query in queries:
        hit = geocode(query)
        if not hit or not _same_state(hit, state):
            continue
        km = None
        if has_centroid:
            km = haversine_km(
                hit.latitude,
                hit.longitude,
                float(district_row["latitude"]),
                float(district_row["longitude"]),
            )
            if km > max_km:
                continue
        row.update(
            latitude=hit.latitude,
            longitude=hit.longitude,
            geo_precision="market",
            query_used=query,
            matched_name=hit.display_name,
            km_from_district="" if km is None else round(km, 1),
        )
        return row
    if has_centroid:
        row.update(
            latitude=district_row["latitude"],
            longitude=district_row["longitude"],
            geo_precision="district_centroid",
            query_used=district_row["query_used"],
            matched_name=district_row["matched_name"],
            km_from_district=0,
        )
    return row


def canonical_markets(aliases_csv: Path = ALIASES) -> list[tuple[str, str, str]]:
    """(state, district, market) for every canonical market in the alias file."""
    df = pd.read_csv(aliases_csv)
    keys = df[["state", "district", "market_canonical"]].drop_duplicates()
    return sorted(map(tuple, keys.itertuples(index=False)))


def geocode_markets(
    markets: list[tuple[str, str, str]],
    geocode: Geocoder,
    market_cache: Path = MARKET_CACHE,
    district_cache: Path = DISTRICT_CACHE,
    max_km: float | None = None,
    retry: frozenset[str] = frozenset(),
    progress: Callable[[str], None] = print,
) -> int:
    """Geocode every market not yet in the cache. Returns the number geocoded this run.

    `retry` lists cached geo_precision values to redo, e.g. {"not_found"}; districts that
    previously failed are then retried too.
    """
    max_km = max_km if max_km is not None else get_settings()["geo"]["max_km_from_district"]
    done = _read_cache(market_cache, ["state", "district", "market"])
    done = {k: v for k, v in done.items() if v["geo_precision"] not in retry}
    todo = [m for m in markets if m not in done]
    progress(f"{len(markets)} markets, {len(markets) - len(todo)} cached, {len(todo)} to do")
    started = time.monotonic()
    for i, (state, district, market) in enumerate(todo, 1):
        district_row = geocode_district(
            state, district, geocode, district_cache, retry_failed=bool(retry)
        )
        row = geocode_market(state, district, market, geocode, district_row, max_km)
        row["geocoded_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        _append(market_cache, MARKET_FIELDS, row)
        if i % 25 == 0 or i == len(todo):
            progress(
                f"  {i}/{len(todo)}  ({time.monotonic() - started:.0f}s)  "
                f"last: {market}, {district} -> {row['geo_precision']}"
            )
    if retry:
        _dedupe_keep_last(market_cache, ["state", "district", "market"])
        _dedupe_keep_last(district_cache, ["state", "district"])
    return len(todo)


def _dedupe_keep_last(path: Path, key: list[str]) -> None:
    if path.exists():
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df.drop_duplicates(key, keep="last").to_csv(path, index=False)


def load_market_geo(market_cache: Path = MARKET_CACHE, overrides: Path = OVERRIDES) -> pd.DataFrame:
    """Cached geocodes with manual overrides applied (overrides win)."""
    geo = pd.read_csv(market_cache)
    if overrides.exists():
        ov = pd.read_csv(overrides)
        if len(ov):
            key = ["state", "district", "market"]
            geo = geo.set_index(key)
            ov = ov.set_index(key)
            geo.loc[ov.index.intersection(geo.index), ["latitude", "longitude"]] = ov[
                ["latitude", "longitude"]
            ]
            geo.loc[ov.index.intersection(geo.index), "geo_precision"] = "manual"
            geo = geo.reset_index()
    return geo


def coverage_report(geo: pd.DataFrame) -> pd.DataFrame:
    """Number and share of markets by geo_precision."""
    counts = (
        geo["geo_precision"]
        .value_counts()
        .rename_axis("geo_precision")
        .reset_index(name="n_markets")
    )
    counts["pct"] = (100 * counts["n_markets"] / len(geo)).round(1)
    return counts
