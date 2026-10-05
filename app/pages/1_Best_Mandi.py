"""Best Mandi: where does my crop fetch the most, after transport and fees?"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402
from data import (  # noqa: E402
    COMMODITIES,
    UNIT,
    haversine_km,
    load,
    market_options,
    page_setup,
    read_csv,
    rupees,
    settings,
)

page_setup("Best Mandi this week", icon="📍")
st.markdown(
    "Choose your crop and the market you would normally sell at. We compare it with every other "
    "market nearby, using each market's **latest reported price**, and subtract the cost of "
    "getting there and the commission/market fees."
)

cfg = settings()
markets = load("markets")
prices = load("latest_prices")
suspect = load("suspect_series")
road_factor = cfg["geo"]["road_factor"]

left, right = st.columns([1, 2])
with left:
    crop = st.selectbox("Crop", COMMODITIES)
    have = prices[prices["commodity"] == crop]
    options = market_options(markets[markets["market_key"].isin(have["market_key"])])
    if not options:
        st.warning(f"No market reported a {crop.lower()} price in the last 30 days of the data.")
        st.stop()
    home_key = st.selectbox(
        "Your market (State › District › Market)",
        list(options),
        format_func=options.get,
        help="Type to search.",
    )
    max_km = st.slider("Maximum road distance (km)", 20, 150, 100, step=10)
    scenario = st.radio(
        "Transport cost", ["Low", "Mid", "High", "Custom"], index=1, horizontal=True
    )
    if scenario == "Custom":
        per_km = st.number_input("Freight, ₹ per quintal per km", 0.0, 10.0, 1.5, 0.1)
        fixed = st.number_input("Loading/handling, ₹ per quintal", 0.0, 500.0, 50.0, 10.0)
        fee_pct = st.number_input("Commission + market fees, % of sale", 0.0, 20.0, 6.0, 0.5) / 100
    else:
        s = cfg["opportunity"]["scenarios"][scenario.lower()]
        per_km, fixed, fee_pct = s["cost_per_qtl_km"], s["fixed_cost_per_qtl"], s["fee_pct"]
    st.caption(f"Using ₹{per_km}/qtl/km freight + ₹{fixed:.0f}/qtl handling + {fee_pct:.0%} fees.")

home = markets.set_index("market_key").loc[home_key]
home_price = have.set_index("market_key").loc[home_key]

cand = have.merge(markets.drop(columns=["last_report_date"]), on="market_key")
cand = cand[cand["market_key"] != home_key]
cand["road_km"] = [
    road_factor * haversine_km(home["latitude"], home["longitude"], la, lo)
    for la, lo in zip(cand["latitude"], cand["longitude"], strict=True)
]
same_town = cand["town_key"] == home["town_key"]
suspect_keys = set(suspect.loc[suspect["commodity"] == crop, "market_key"])
is_suspect = cand["market_key"].isin(suspect_keys)
cand = cand[~same_town & ~is_suspect & (cand["road_km"] <= max_km)].copy()

cand["transport"] = cand["road_km"] * per_km + fixed
cand["fees"] = cand["last_price"] * fee_pct
cand["net_price"] = cand["last_price"] - cand["transport"] - cand["fees"]
cand["gain_vs_home"] = cand["net_price"] - home_price["last_price"]
cand = cand.sort_values("net_price", ascending=False)

with right:
    a, b, c = st.columns(3)
    a.metric(
        "Your market's latest price",
        rupees(home_price["last_price"]),
        help=f"Reported on {home_price['last_report_date']:%d %b %Y}. {UNIT}.",
    )
    better = cand[cand["gain_vs_home"] > 0]
    b.metric("Markets paying more (net)", f"{len(better)} of {len(cand)}")
    c.metric(
        "Best net gain",
        rupees(better["gain_vs_home"].max()) if len(better) else "none",
        help="Extra ₹ per quintal after transport and fees, versus selling at home.",
    )

    persistence = read_csv("reports/tables/phase3/sanity_05_actionable_opportunities.csv")
    lo, hi = (
        persistence["pct_signal_still_opportunity"].min(),
        persistence["pct_signal_still_opportunity"].max(),
    )
    st.caption(
        f"Historically, when a destination was profitable, it was still profitable at the next "
        f"report **{lo:.0f}–{hi:.0f}%** of the time (2018–2025, mid-cost scenario). Prices change: "
        "check the latest report date before you travel."
    )

    show = cand.head(25).assign(
        Market=lambda d: d["market"] + " (" + d["district"] + ", " + d["state"] + ")",
        **{
            "Road km": lambda d: d["road_km"].round(0).astype(int),
            "Latest price": lambda d: d["last_price"].map(rupees),
            "Transport": lambda d: d["transport"].map(rupees),
            "Fees": lambda d: d["fees"].map(rupees),
            "Net price": lambda d: d["net_price"].map(rupees),
            "Gain vs home": lambda d: d["gain_vs_home"].map(
                lambda v: ("+" if v > 0 else "−" if v < 0 else "") + rupees(abs(v))
            ),
            "Last report": lambda d: d["last_report_date"].dt.strftime("%d %b %Y"),
            "Report days (last 30)": lambda d: d["report_days_last_30"].astype(int),
        },
    )
    st.dataframe(
        show[
            [
                "Market",
                "Road km",
                "Latest price",
                "Transport",
                "Fees",
                "Net price",
                "Gain vs home",
                "Last report",
                "Report days (last 30)",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    notes = []
    if same_town.any():
        notes.append(
            f"{int(same_town.sum())} yard(s) in the same town as your market are not shown (same place)."
        )
    if is_suspect.any():
        notes.append(
            f"{int(is_suspect.sum())} market(s) excluded: their prices look unreliable "
            "(persistently far below the state level; being checked)."
        )
    notes.append(
        f"Prices in {UNIT}. Road distance = straight-line distance × {road_factor} (estimate)."
    )
    st.caption(" ".join(notes))

map_df = pd.concat(
    [
        pd.DataFrame(
            {
                "name": [f"Your market: {home['market']}"],
                "lat": [home["latitude"]],
                "lon": [home["longitude"]],
                "color": [[11, 11, 11, 230]],
                "size": [9000],
            }
        ),
        pd.DataFrame(
            {
                "name": cand["market"] + ": net " + cand["net_price"].map(rupees),
                "lat": cand["latitude"],
                "lon": cand["longitude"],
                "color": [
                    [42, 120, 214, 210] if g > 0 else [137, 135, 129, 160]
                    for g in cand["gain_vs_home"]
                ],
                "size": 6000,
            }
        ),
    ],
    ignore_index=True,
)
st.subheader("Map")
st.caption("Black = your market. Blue = pays more after costs. Grey = pays less.")
st.pydeck_chart(
    pdk.Deck(
        map_provider="carto",
        map_style=pdk.map_styles.CARTO_LIGHT,
        initial_view_state=pdk.ViewState(
            latitude=float(home["latitude"]), longitude=float(home["longitude"]), zoom=7
        ),
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                map_df,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius="size",
                pickable=True,
            )
        ],
        tooltip={"text": "{name}"},
    )
)
