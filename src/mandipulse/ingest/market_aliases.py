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


# --- Review step (user rule, 2026-10-02) -----------------------------------------------------
# A flagged pair is merged only if (a) both names are in the same district after district
# corrections AND (b) they never report on the same date (any commodity). The check is made
# against everything already merged into the target, so chains of renames stay date-disjoint.
# Explicit user decisions in market_review_overrides.csv take precedence.

DISTRICT_CORRECTIONS_CSV = PROJECT_ROOT / "data" / "reference" / "district_corrections.csv"
REVIEW_OVERRIDES_CSV = PROJECT_ROOT / "data" / "reference" / "market_review_overrides.csv"
REVIEW_CSV = PROJECT_ROOT / "reports" / "tables" / "phase1" / "market_alias_review.csv"
DATES_QUERY = PROJECT_ROOT / "analysis" / "queries" / "phase1" / "raw_market_dates.sql"

RawKey = tuple[str, str, str]  # (state, district_raw, market_raw)


def apply_review(
    names: list[MarketName],
    dates: dict[RawKey, set[date]],
    corrections: pd.DataFrame,
    overrides: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (aliases, review). `names` carry RAW districts; corrections relabel some."""
    fix = {
        (r.state, r.district_raw, r.market_raw): r.district_corrected
        for r in corrections.itertuples()
    }
    plain = [n for n in names if (n.state, n.district, n.market) not in fix]
    moved = [n for n in names if (n.state, n.district, n.market) in fix]

    aliases = build_aliases(plain)
    aliases.insert(1, "district_raw", aliases["district"])
    aliases["review_decision"] = ""

    # Units of identity: (state, district, canonical) -> raw keys and their report dates.
    def unit_dates(state: str, district: str, canonical: str) -> set[date]:
        rows = aliases[
            (aliases.state == state)
            & (aliases.district == district)
            & (aliases.market_canonical == canonical)
        ]
        out: set[date] = set()
        for r in rows.itertuples():
            out |= dates.get((r.state, r.district_raw, r.market_raw), set())
        return out

    override = {
        (r.state, r.district, r.market_canonical, r.target_canonical): (r.decision, r.reason)
        for r in overrides.itertuples()
    }
    review_rows = []

    def decide(state, district, flagged, target, flagged_dates, same_district, flag_reason):
        target_dates = unit_dates(state, district, target)
        shared = len(flagged_dates & target_dates)
        user = override.get((state, district, flagged, target))
        if user:
            decision, reason = user
        elif not same_district:
            decision, reason = "keep_separate", "different district"
        elif shared:
            decision, reason = "keep_separate", f"reports on {shared} same date(s) as target"
        else:
            decision, reason = "merge", "same district, never reports on the same date"
        review_rows.append(
            {
                "state": state,
                "district": district,
                "flagged_canonical": flagged,
                "target_canonical": target,
                "flag_reason": flag_reason,
                "n_report_days": len(flagged_dates),
                "n_target_report_days": len(target_dates),
                "n_shared_dates": shared,
                "decision": decision,
                "reason": reason,
            }
        )
        return decision

    # 1) Names flagged by build_aliases, oldest first so renames chain in time order.
    flagged = (
        aliases[aliases.needs_review]
        .groupby(["state", "district", "market_canonical"], as_index=False)
        .agg(
            target=("suggested_canonical", "first"),
            target_district=("suggested_district", "first"),
            flag_reason=("review_reason", "first"),
            first=("first_date", "min"),
        )
        .sort_values(["first", "market_canonical"])
    )
    for f in flagged.itertuples():
        mask = (
            (aliases.state == f.state)
            & (aliases.district == f.district)
            & (aliases.market_canonical == f.market_canonical)
        )
        own = unit_dates(f.state, f.district, f.market_canonical)
        same = f.target_district == f.district
        decision = decide(
            f.state, f.district, f.market_canonical, f.target, own, same, f.flag_reason
        )
        aliases.loc[mask, "review_decision"] = decision
        if decision == "merge":
            aliases.loc[mask, "market_canonical"] = f.target
            aliases.loc[mask, "rule"] = "reviewed_merge"

    # 2) Names whose district was corrected: merge into a same-named market in the corrected
    #    district if the date rule allows; otherwise keep them apart under '<name> (ex-<district>)'.
    for n in sorted(moved, key=lambda n: n.first_date):
        new_district = fix[(n.state, n.district, n.market)]
        base = strip_apmc(n.market)
        own = dates.get((n.state, n.district, n.market), set())
        twins = aliases[
            (aliases.state == n.state)
            & (aliases.district == new_district)
            & (aliases.market_canonical.map(match_key) == match_key(base))
        ]
        canonical, decision = base, "district_corrected"
        if len(twins):
            target = twins.market_canonical.iloc[0]
            decision = decide(
                n.state,
                new_district,
                f"{base} [{n.district} record]",
                target,
                own,
                True,
                "district_corrected",
            )
            canonical = target if decision == "merge" else f"{base} (ex-{n.district})"
        aliases.loc[len(aliases)] = {
            "state": n.state,
            "district_raw": n.district,
            "district": new_district,
            "market_raw": n.market,
            "market_canonical": canonical,
            "rule": "district_corrected" + ("+reviewed_merge" if decision == "merge" else ""),
            "needs_review": False,
            "review_reason": "",
            "suggested_canonical": "",
            "suggested_district": "",
            "n_rows": n.n_rows,
            "first_date": n.first_date,
            "last_date": n.last_date,
            "review_decision": decision,
        }

    aliases["needs_review"] = False  # every flag now carries a recorded decision
    aliases = aliases.sort_values(["state", "district", "market_canonical", "market_raw"])
    return aliases.reset_index(drop=True), pd.DataFrame(review_rows)


def build_aliases_from_db(out: Path = ALIASES_CSV, review_out: Path = REVIEW_CSV) -> pd.DataFrame:
    from mandipulse.db import get_engine

    engine = get_engine()
    df = pd.read_sql(NAMES_QUERY.read_text(encoding="utf-8"), engine)  # ~1000 rows
    names = [
        MarketName(r.state, r.district, r.market, int(r.n_rows), r.first_date, r.last_date)
        for r in df.itertuples()
    ]
    days = pd.read_sql(DATES_QUERY.read_text(encoding="utf-8"), engine)  # ~0.8M small rows
    dates = days.groupby(["state", "district", "market"]).arrival_date.agg(set).to_dict()
    aliases, review = apply_review(
        names, dates, pd.read_csv(DISTRICT_CORRECTIONS_CSV), pd.read_csv(REVIEW_OVERRIDES_CSV)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    aliases.to_csv(out, index=False)
    review.to_csv(review_out, index=False)
    return aliases
