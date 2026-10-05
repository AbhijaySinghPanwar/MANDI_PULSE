"""Mandi Pulse: home page.   Run:  streamlit run app/Home.py"""

import streamlit as st
from data import COMMODITIES, load, page_setup

page_setup("Mandi Pulse", icon="🧅")

st.markdown(
    """
**Which mandi pays the most for my crop this week, after transport and fees?**

Mandi Pulse uses official daily wholesale prices (Agmarknet) for **tomato, onion and potato** in
**Maharashtra, Madhya Pradesh, Uttar Pradesh and Gujarat** to help farmers, FPOs and traders
compare nearby markets, see where prices are heading, and spot price crashes early.
"""
)

meta = load("meta")
markets = load("markets")
c1, c2, c3 = st.columns(3)
c1.metric("Markets tracked", f"{len(markets):,}")
c2.metric("Market-days of prices", f"{int(meta['n_market_days'].iloc[0]):,}")
c3.metric("Crops", " · ".join(COMMODITIES))

st.subheader("What you can do here")
st.markdown(
    """
| Page | Use it to… |
|---|---|
| **Best Mandi** | Pick your crop and your home market and see which markets nearby pay more **after transport and commission**. |
| **Price Outlook** | See recent prices for a market and the forecast for the next 7 days, with a likely range. |
| **Crash Risk** | See markets where prices are **falling now**, and an **early warning** list of markets that may crash in the next 2 weeks. |
| **Market Explorer** | Find districts stuck with low prices and few markets nearby, and see what kind of market each one is. |
| **Methodology** | Data sources, how the data was cleaned, the assumptions, and how good the models are. |
"""
)
st.caption(
    "Prices are wholesale modal prices. They are an indicator, not the price an individual farmer "
    "will get: quality, grade and the commission agent also matter."
)
