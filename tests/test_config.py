"""Smoke tests for config loading. They run without the (gitignored) Kaggle archive."""

from mandipulse.config import get_settings


def test_scope_uses_exact_archive_spellings():
    scope = get_settings()["scope"]
    assert scope["commodities"] == ["Tomato", "Onion", "Potato"]
    # Look-alike commodities in the archive must never be in scope.
    assert "Onion Green" not in scope["commodities"]
    assert "Sweet Potato" not in scope["commodities"]


def test_sources_are_ordered_and_external_apis_disabled():
    sources = get_settings()["sources"]
    assert list(sources) == ["kaggle", "ceda", "datagov"]
    assert sources["ceda"]["enabled"] is False
    assert sources["datagov"]["enabled"] is False


def test_cost_scenarios_are_ordered_low_to_high():
    s = get_settings()["opportunity"]["scenarios"]
    assert s["low"]["cost_per_qtl_km"] < s["mid"]["cost_per_qtl_km"] < s["high"]["cost_per_qtl_km"]
