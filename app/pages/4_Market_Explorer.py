"""Market Explorer: price-trapped districts (Q4) and market segments (Model C)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402
from data import COMMODITIES, load, page_setup, settings  # noqa: E402

page_setup("Market Explorer", icon="🗺️")

SEGMENTS = {
    "Stable, regular market": "Reports almost every day, prices close to the state level and steady. The safest benchmark.",
    "Volatile & crash-prone": "Reports regularly, but prices swing a lot and crash more often than elsewhere. Watch the Crash Risk page.",
    "Under-priced, sparse reporting": "Prices usually below the state level and reported on fewer days, even though other markets are nearby. Compare before selling here.",
    "Isolated premium market": "Few other markets within 50 km, prices usually above the state level, reported on fewer days.",
    "Erratic & under-priced, thin reporting": "Rare reports, very large swings and low prices. Many of these series may have data problems; treat their prices with caution.",
}

access = load("district_access")
clusters = load("clusters")
cfg = settings()["district_access"]

c1, c2 = st.columns(2)
crop = c1.selectbox("Crop", COMMODITIES)
state = c2.selectbox("State", ["All states", *sorted(access["state"].unique())])

tab1, tab2 = st.tabs(["Price-trapped districts", "Market segments"])

with tab1:
    st.markdown(
        f"A district is **price-trapped** when it has **{cfg['trapped_max_markets']} or fewer** market "
        f"towns with prices within {cfg['near_radius_km']} km, **and** its prices are on average "
        f"**below {cfg['trapped_max_price_index']:.0%}** of the state's on the same days."
    )
    a = access[access["commodity"] == crop]
    if state != "All states":
        a = a[a["state"] == state]
    trapped = a[a["is_price_trapped"]].sort_values("avg_price_index")
    st.metric(f"Price-trapped districts ({crop.lower()})", f"{len(trapped)} of {len(a)}")
    view = a.sort_values(["is_price_trapped", "avg_price_index"], ascending=[False, True]).assign(
        **{
            "Price vs state": lambda d: d["avg_price_index"].map(lambda v: f"{v:.0%}"),
            "Days a nearby market paid more": lambda d: d["opportunity_rate"].map(
                lambda v: "–" if v != v else f"{v:.0%}"
            ),
            "Price-trapped": lambda d: d["is_price_trapped"].map({True: "Yes", False: ""}),
            "n_markets_within_50km": lambda d: d["n_markets_within_50km"].astype(int),
        }
    )
    st.dataframe(
        view[
            [
                "state",
                "district",
                "n_markets_within_50km",
                "Price vs state",
                "Days a nearby market paid more",
                "Price-trapped",
            ]
        ].rename(
            columns={
                "state": "State",
                "district": "District",
                "n_markets_within_50km": "Market towns within 50 km",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "'Days a nearby market paid more' = share of market-days with a market within 100 km paying more after transport and 6% fees."
    )

with tab2:
    st.markdown("Every market × crop with enough history is grouped into one of five types:")
    for name, text in SEGMENTS.items():
        st.markdown(f"- **{name}**: {text}")
    k = clusters[clusters["commodity"] == crop]
    if state != "All states":
        k = k[k["state"] == state]
    st.bar_chart(k["cluster_name"].value_counts().rename("markets"), horizontal=True)
    seg = st.selectbox("Show markets of type", ["All types", *SEGMENTS])
    if seg != "All types":
        k = k[k["cluster_name"] == seg]
    st.dataframe(
        k.assign(
            **{
                "Price vs state": k["price_index"].map(lambda v: f"{v:.0%}"),
                "Reports on % of days": k["report_freq"].map(lambda v: f"{v:.0%}"),
                "Crash rate": k["crash_rate"].map(lambda v: f"{v:.0%}"),
            }
        )[
            [
                "state",
                "district",
                "market",
                "cluster_name",
                "Price vs state",
                "Reports on % of days",
                "Crash rate",
            ]
        ].rename(
            columns={
                "state": "State",
                "district": "District",
                "market": "Market",
                "cluster_name": "Type",
            }
        ),
        hide_index=True,
        width="stretch",
    )
