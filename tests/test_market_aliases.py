"""Market alias rules, on small synthetic name lists."""

from datetime import date

from mandipulse.ingest.market_aliases import MarketName, build_aliases, clean, strip_apmc

OLD = (date(2018, 1, 1), date(2025, 11, 4))
NEW = (date(2025, 11, 29), date(2026, 4, 20))


def name(market, district="Nashik", span=OLD, n=100, state="Maharashtra"):
    return MarketName(state, district, market, n, *span)


def mapping(df):
    return dict(zip(df.market_raw, df.market_canonical, strict=True))


def test_clean_and_strip():
    assert clean("Sendhwa (F&amp;V)  APMC ") == "Sendhwa (F&V) APMC"
    assert strip_apmc("Sendhwa (F&amp;V) APMC") == "Sendhwa (F&V)"
    assert strip_apmc("Lasalgaon") == "Lasalgaon"


def test_apmc_suffix_merges_with_pre_change_name():
    df = build_aliases([name("Lasalgaon"), name("Lasalgaon APMC", span=NEW, n=30)])
    assert mapping(df) == {"Lasalgaon": "Lasalgaon", "Lasalgaon APMC": "Lasalgaon"}
    rules = dict(zip(df.market_raw, df.rule, strict=True))
    assert rules == {"Lasalgaon": "identity", "Lasalgaon APMC": "apmc_suffix"}
    assert not df.needs_review.any()


def test_html_entity_variant_merges():
    df = build_aliases(
        [name("Sendhwa (F&V)", "Badwani"), name("Sendhwa (F&amp;V) APMC", "Badwani", span=NEW)]
    )
    assert set(df.market_canonical) == {"Sendhwa (F&V)"}


def test_new_market_only_seen_with_suffix_gets_suffix_removed():
    df = build_aliases([name("Bisoli APMC", "Badaun", span=NEW, state="Uttar Pradesh")])
    assert mapping(df) == {"Bisoli APMC": "Bisoli"}
    assert df.rule.tolist() == ["apmc_suffix_only"]


def test_sub_yards_in_brackets_stay_separate():
    # Same town, different sub-yards, reporting at the same time: distinct markets, no flag.
    df = build_aliases([name("Pune (Pimpri)", "Pune"), name("Pune (Manjri)", "Pune")])
    assert mapping(df) == {"Pune (Pimpri)": "Pune (Pimpri)", "Pune (Manjri)": "Pune (Manjri)"}
    assert not df.needs_review.any()


def test_suffix_only_matches_within_same_district():
    df = build_aliases([name("Kalyan", "Thane"), name("Kalyan APMC", "Pune", span=NEW)])
    assert mapping(df) == {"Kalyan": "Kalyan", "Kalyan APMC": "Kalyan"}
    # Same canonical text, but different districts: still two separate markets...
    assert df.groupby(["district", "market_canonical"]).ngroups == 2
    # ...and the later one is flagged for review, not merged.
    flagged = df[df.needs_review]
    assert flagged.market_raw.tolist() == ["Kalyan APMC"]
    assert flagged.review_reason.tolist() == ["same_name_other_district"]
    assert flagged.suggested_district.tolist() == ["Thane"]


def test_likely_rename_is_flagged_not_merged():
    df = build_aliases(
        [
            name("Chhindwara (F&V)", "Chhindwara", span=(date(2018, 1, 1), date(2023, 12, 20))),
            name("Chindwara (F&V)", "Chhindwara", span=(date(2024, 10, 11), date(2025, 11, 2))),
        ]
    )
    assert mapping(df) == {
        "Chhindwara (F&V)": "Chhindwara (F&V)",
        "Chindwara (F&V)": "Chindwara (F&V)",
    }
    flagged = df[df.needs_review]
    assert flagged.market_raw.tolist() == ["Chindwara (F&V)"]
    assert flagged.suggested_canonical.tolist() == ["Chhindwara (F&V)"]
    assert flagged.review_reason.tolist() == ["similar_name_no_overlap"]


def test_similar_names_reporting_at_the_same_time_are_not_flagged():
    df = build_aliases([name("Lasalgaon (Niphad)"), name("Lasalgaon (Vinchur)")])
    assert not df.needs_review.any()


def test_every_raw_name_gets_exactly_one_canonical():
    names = [
        name("Lasalgaon"),
        name("Lasalgaon APMC", span=NEW),
        name("Manmad"),
        name("Manmad APMC", span=NEW),
        name("Nasik"),
    ]
    df = build_aliases(names)
    assert len(df) == len(names)
    assert df.market_raw.is_unique
    assert df.market_canonical.notna().all()
