"""Review rule for flagged market names (user decision 2026-10-02): merge only if same district
after district corrections AND never reporting on the same date; user overrides win."""

from datetime import date

import pandas as pd

from mandipulse.geo.geocode import market_names
from mandipulse.ingest.market_aliases import MarketName, apply_review

STATE = "Madhya Pradesh"
NO_CORRECTIONS = pd.DataFrame(columns=["state", "district_raw", "market_raw", "district_corrected"])
NO_OVERRIDES = pd.DataFrame(
    columns=["state", "district", "market_canonical", "target_canonical", "decision", "reason"]
)


def name(market, district, start, end):
    return MarketName(STATE, district, market, 100, start, end)


def days(*ds):
    return {date(2024, 1, d) for d in ds}


def canon(aliases, raw, district_raw=None):
    rows = aliases[aliases.market_raw == raw]
    if district_raw:
        rows = rows[rows.district_raw == district_raw]
    return rows.market_canonical.item()


def test_rename_without_shared_dates_is_merged():
    names = [
        name("Sendhwa", "Badwani", date(2018, 1, 1), date(2023, 12, 20)),
        name("Sendhwa (F&V)", "Badwani", date(2024, 9, 23), date(2025, 11, 2)),
    ]
    dates = {
        (STATE, "Badwani", "Sendhwa"): days(1, 2),
        (STATE, "Badwani", "Sendhwa (F&V)"): days(3, 4),
    }
    aliases, review = apply_review(names, dates, NO_CORRECTIONS, NO_OVERRIDES)
    assert canon(aliases, "Sendhwa (F&V)") == "Sendhwa"
    assert review.decision.tolist() == ["merge"]
    assert not aliases.needs_review.any()


def test_one_shared_date_keeps_names_separate():
    names = [
        name("Sajapur", "Shajapur", date(2023, 12, 21), date(2024, 7, 1)),
        name("Shajapur", "Shajapur", date(2024, 7, 1), date(2025, 11, 4)),
    ]
    dates = {
        (STATE, "Shajapur", "Sajapur"): days(1, 2),
        (STATE, "Shajapur", "Shajapur"): days(2, 3),
    }
    aliases, review = apply_review(names, dates, NO_CORRECTIONS, NO_OVERRIDES)
    assert canon(aliases, "Shajapur") == "Shajapur"
    assert review.n_shared_dates.tolist() == [1]
    assert review.decision.tolist() == ["keep_separate"]


def test_chain_must_be_disjoint_from_everything_already_merged():
    # Two later names point at the same target; the second overlaps the first merged one.
    names = [
        name("Chhindwara (F&V)", "Chhindwara", date(2018, 1, 1), date(2023, 12, 20)),
        name("Chindwara (F&V)", "Chhindwara", date(2024, 10, 11), date(2025, 11, 2)),
        name("Chhindwara", "Chhindwara", date(2024, 12, 17), date(2025, 1, 9)),
    ]
    dates = {
        (STATE, "Chhindwara", "Chhindwara (F&V)"): days(1),
        (STATE, "Chhindwara", "Chindwara (F&V)"): days(5, 6),
        (STATE, "Chhindwara", "Chhindwara"): days(6),
    }
    aliases, review = apply_review(names, dates, NO_CORRECTIONS, NO_OVERRIDES)
    assert canon(aliases, "Chindwara (F&V)") == "Chhindwara (F&V)"
    assert canon(aliases, "Chhindwara") == "Chhindwara"
    assert dict(zip(review.flagged_canonical, review.decision, strict=True)) == {
        "Chindwara (F&V)": "merge",
        "Chhindwara": "keep_separate",
    }


def test_user_override_wins_over_the_rule():
    names = [
        name("Manawar", "Dhar", date(2018, 1, 1), date(2023, 12, 20)),
        name("Badnawar", "Dhar", date(2023, 12, 27), date(2025, 11, 3)),
    ]
    dates = {(STATE, "Dhar", "Manawar"): days(1), (STATE, "Dhar", "Badnawar"): days(2)}
    overrides = pd.DataFrame(
        [
            {
                "state": STATE,
                "district": "Dhar",
                "market_canonical": "Badnawar",
                "target_canonical": "Manawar",
                "decision": "keep_separate",
                "reason": "different towns",
            }
        ]
    )
    aliases, review = apply_review(names, dates, NO_CORRECTIONS, overrides)
    assert canon(aliases, "Badnawar") == "Badnawar"
    assert review.reason.tolist() == ["different towns"]


def test_district_correction_then_rule():
    names = [
        name("Jangipura", "Hapur", date(2018, 1, 1), date(2024, 4, 26)),
        name("Jangipura", "Ghazipur", date(2025, 2, 28), date(2025, 10, 17)),
        name("Gazipur", "Hapur", date(2018, 1, 1), date(2024, 5, 14)),
        name("Gazipur", "Ghazipur", date(2024, 5, 1), date(2025, 11, 4)),
    ]
    dates = {
        (STATE, "Hapur", "Jangipura"): days(1),
        (STATE, "Ghazipur", "Jangipura"): days(2),
        (STATE, "Hapur", "Gazipur"): days(1, 2),
        (STATE, "Ghazipur", "Gazipur"): days(2, 3),
    }
    corrections = pd.DataFrame(
        [
            {
                "state": STATE,
                "district_raw": "Hapur",
                "market_raw": m,
                "district_corrected": "Ghazipur",
            }
            for m in ("Jangipura", "Gazipur")
        ]
    )
    aliases, review = apply_review(names, dates, corrections, NO_OVERRIDES)
    moved = aliases[aliases.district_raw == "Hapur"].set_index("market_raw")
    assert set(moved.district) == {"Ghazipur"}
    assert moved.loc["Jangipura", "market_canonical"] == "Jangipura"  # merged
    assert moved.loc["Gazipur", "market_canonical"] == "Gazipur (ex-Hapur)"  # overlap: kept apart
    assert sorted(review.decision) == ["keep_separate", "merge"]


def test_ex_district_marker_is_not_geocoded_as_a_place():
    assert market_names("Gazipur (ex-Hapur)") == ["Gazipur"]
