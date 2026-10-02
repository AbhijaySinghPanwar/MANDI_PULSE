"""Map every raw market name to one canonical name per (state, district).

From Nov 2025 the archive renames markets 'X' -> 'X APMC' (sometimes with HTML entities,
e.g. 'Sendhwa (F&amp;V) APMC'). Parenthetical parts are kept because they identify distinct
sub-yards ('Pune (Pimpri)' and 'Pune (Manjri)' report side by side for years).

Merge rules (certain, applied automatically, within one state x district):
  identity          the name is already canonical
  apmc_suffix       'X APMC' where 'X' also exists        -> X
  apmc_suffix_only  'X APMC' with no pre-change twin      -> X (suffix removed, nothing merged)
  normalised_match  differs only by case / spacing / punctuation / HTML entities

Doubtful cases are NEVER merged. They keep their own canonical name and are flagged
needs_review = True with a suggestion:
  similar_name_no_overlap  similar names in the same district whose reporting periods do not
                           overlap (looks like a rename, e.g.
                           'Chhindwara (F&V)' -> 'Chindwara (F&V)')
  same_name_other_district same canonical name in another district of the state, with
                           non-overlapping periods (looks like a district relabel)
"""

import html
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from mandipulse.config import PROJECT_ROOT

NAMES_QUERY = PROJECT_ROOT / "analysis" / "queries" / "phase1" / "raw_market_names.sql"
ALIASES_CSV = PROJECT_ROOT / "data" / "reference" / "market_aliases.csv"

SIMILARITY_THRESHOLD = 0.8
MAX_OVERLAP_DAYS = 31  # periods overlapping by more than this are treated as different markets

_APMC_SUFFIX = re.compile(r"\s+APMC$", re.IGNORECASE)


def clean(name: str) -> str:
    """Unescape HTML entities and collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(name)).strip()


def strip_apmc(name: str) -> str:
    return _APMC_SUFFIX.sub("", clean(name))


def match_key(name: str) -> str:
    """Comparison key: lowercase letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", strip_apmc(name).lower())


def core_key(name: str) -> str:
    """Key of the part before any parenthesis: 'Damoh (F&V)' -> 'damoh'."""
    return match_key(strip_apmc(name).split("(")[0])


@dataclass
class MarketName:
    state: str
    district: str
    market: str
    n_rows: int
    first_date: date
    last_date: date


@dataclass
class _Group:
    """All raw names in one (state, district) that share a match_key."""

    state: str
    district: str
    members: list[MarketName] = field(default_factory=list)
    canonical: str = ""
    review_reason: str = ""
    suggested_canonical: str = ""
    suggested_district: str = ""

    @property
    def first(self) -> date:
        return min(m.first_date for m in self.members)

    @property
    def last(self) -> date:
        return max(m.last_date for m in self.members)

    @property
    def n_rows(self) -> int:
        return sum(m.n_rows for m in self.members)


def _overlap_days(a: _Group, b: _Group) -> int:
    return (min(a.last, b.last) - max(a.first, b.first)).days


def _similar(a: str, b: str) -> bool:
    ka, kb = match_key(a), match_key(b)
    if core_key(a) == core_key(b) and core_key(a):
        return True
    return SequenceMatcher(None, ka, kb).ratio() >= SIMILARITY_THRESHOLD


def build_aliases(names: list[MarketName]) -> pd.DataFrame:
    groups: dict[tuple[str, str, str], _Group] = {}
    for n in names:
        key = (n.state, n.district, match_key(n.market))
        groups.setdefault(key, _Group(n.state, n.district)).members.append(n)

    # Canonical name: the busiest pre-change spelling, else the suffix-stripped name.
    for g in groups.values():
        plain = [m for m in g.members if not _APMC_SUFFIX.search(clean(m.market))]
        best = max(plain or g.members, key=lambda m: (m.n_rows, m.last_date))
        g.canonical = strip_apmc(best.market)

    # Review flags (no merging). The later group is flagged and points at the earlier one.
    by_district: dict[tuple[str, str], list[_Group]] = defaultdict(list)
    by_state_key: dict[tuple[str, str], list[_Group]] = defaultdict(list)
    for g in groups.values():
        by_district[(g.state, g.district)].append(g)
        by_state_key[(g.state, match_key(g.canonical))].append(g)

    def flag(later: _Group, earlier: _Group, reason: str) -> None:
        if not later.review_reason:
            later.review_reason = reason
            later.suggested_canonical = earlier.canonical
            later.suggested_district = earlier.district

    for district_groups in by_district.values():
        ordered = sorted(district_groups, key=lambda g: (g.first, g.canonical))
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if _overlap_days(a, b) <= MAX_OVERLAP_DAYS and _similar(a.canonical, b.canonical):
                    flag(b, a, "similar_name_no_overlap")

    for same_key in by_state_key.values():
        ordered = sorted(same_key, key=lambda g: (g.first, g.district))
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if a.district != b.district and _overlap_days(a, b) <= MAX_OVERLAP_DAYS:
                    flag(b, a, "same_name_other_district")

    rows = []
    for g in groups.values():
        for m in g.members:
            cleaned = clean(m.market)
            if m.market == g.canonical:
                rule = "identity"
            elif strip_apmc(m.market) == g.canonical and cleaned != strip_apmc(m.market):
                twin = any(
                    strip_apmc(o.market) == g.canonical
                    and o is not m
                    and not _APMC_SUFFIX.search(clean(o.market))
                    for o in g.members
                )
                rule = "apmc_suffix" if twin else "apmc_suffix_only"
            else:
                rule = "normalised_match"
            rows.append(
                {
                    "state": m.state,
                    "district": m.district,
                    "market_raw": m.market,
                    "market_canonical": g.canonical,
                    "rule": rule,
                    "needs_review": bool(g.review_reason),
                    "review_reason": g.review_reason,
                    "suggested_canonical": g.suggested_canonical,
                    "suggested_district": g.suggested_district,
                    "n_rows": m.n_rows,
                    "first_date": m.first_date,
                    "last_date": m.last_date,
                }
            )
    columns = [
        "state",
        "district",
        "market_raw",
        "market_canonical",
        "rule",
        "needs_review",
        "review_reason",
        "suggested_canonical",
        "suggested_district",
        "n_rows",
        "first_date",
        "last_date",
    ]
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["state", "district", "market_canonical", "market_raw"])
        .reset_index(drop=True)
    )


def build_aliases_from_db(out: Path = ALIASES_CSV) -> pd.DataFrame:
    from mandipulse.db import get_engine

    df = pd.read_sql(NAMES_QUERY.read_text(encoding="utf-8"), get_engine())  # ~1000 rows
    names = [
        MarketName(r.state, r.district, r.market, int(r.n_rows), r.first_date, r.last_date)
        for r in df.itertuples()
    ]
    aliases = build_aliases(names)
    out.parent.mkdir(parents=True, exist_ok=True)
    aliases.to_csv(out, index=False)
    return aliases
