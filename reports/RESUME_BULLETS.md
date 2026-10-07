# Resume bullets and interview prep

Every number below comes from a saved result in this repository; the source is given in brackets. Do not round them up.

## Resume bullets (pick 3–4)

- **Built an end-to-end price-analytics pipeline (Python, DuckDB, PostgreSQL, dbt)** that filters a 7.6-crore-row Agmarknet archive down to **18.3 lakh daily mandi records across 594 markets in 4 states**. **135 dbt data-quality tests** flag 0.15% of rows as invalid and isolate 22 suspect price series. *[reports/tables/phase2/01_reconciliation.csv; dbt test count]*
- **Quantified hidden price gaps between nearby wholesale markets:** after transport and 6% fees, a mandi within 100 km paid more on **33.8% of market-days** (24.4–42.2% across robustness checks and cost scenarios), with a median gain of **₹370 per quintal**. Also identified **22 "price-trapped" districts**. *[reports/PHASE3_FINDINGS.md]*
- **Developed a LightGBM 7-day price forecast** that cut error by **6.9% vs the best baseline** over 108,004 walk-forward forecasts. Validated the objective on a separate pre-test window, and calibrated the p10–p90 range with conformal prediction (coverage 75.6% → 77.3%). *[reports/ML_REPORT.md]*
- **Built a crash early-warning model** that, on days *before* prices start falling, ranks risk **about 2× better than a seasonal baseline** (PR-AUC 0.29 vs 0.15; 0.25 vs 0.07 outside December): about 3 in 10 alerts come true, **~6.6 days ahead**. Showed that 74% of "crashes" were already under way, and reported the honest metric instead of the flattering one (0.75). *[reports/ml/crash_risk_metrics.json]*
- **Delivered the insights as a 5-page Streamlit decision tool** (best mandi after costs, forecasts, crash alerts), deployable without a database from a 2.7 MB snapshot and smoke-tested on two data backends, **plus a 5-page Power BI dashboard specification**. *[app/, powerbi/DASHBOARD_SPEC.md]*

## 30-second pitch

"Indian farmers usually sell at the nearest mandi without knowing what nearby mandis pay. I took 8 years of government mandi prices for tomato, onion and potato in four states and built a pipeline in Python, Postgres and dbt to clean them; the data had real problems, like a market renaming and a state that turned out to report retail prices. The main finding: on about a third of days, a mandi within 100 km paid more even after transport and commission, typically ₹370 a quintal, and these opportunities persisted day to day. I also built a 7-day price forecast and a crash early-warning model. I'm careful about how I report them: the forecast is only about 7% better than 'next week equals today', and about 3 in 10 crash warnings come true, roughly a week ahead. It all ships as a Streamlit app that tells a farmer which mandi to sell at this week."

## Likely interview questions, with short honest answers

**1. "Your forecast is only 6.9% better than a naive baseline. Why bother?"**
Because the naive baseline is very strong for 7-day vegetable prices: most weeks, prices barely move. The model's value is in the weeks they do move. It also gives a calibrated range (about 77% coverage against an 80% target), which the naive rule cannot. I report the 6.9% plainly. In a shock like the July 2023 tomato spike, every method lagged, and the model was only 3.6% better. I would not sell it as more than "a modestly better guide".

**2. "Did you tune on the test set?"**
Once, and I caught it. After the first run I switched the objective from mean (L2) to median (L1), having seen the test months. To check that choice, I re-ran both objectives on a separate window, Nov 2024 – Apr 2025, using only data before the test period. L1 won there too: 4.5% lower error, better in all 6 months. So the choice stands without the test set. The band calibration was also fitted only on that earlier window. One side effect I did not "fix": it slightly narrowed potato's band, and potato's test coverage dropped. Changing the method after seeing that would have been tuning on the test set again.

**3. "A 34% (tomato: 43%) opportunity rate sounds too high. Is it real?"**
It is the share of market-days on which *at least one* of about 8 neighbours within 100 km paid more after costs. Any single neighbour pays more on only 11.9% of days, so it is "best of 8", not "a typical alternative". I stress-tested it:
- comparing only the same variety drops it to 24.4%, so part of the gap is quality, not a missed opportunity;
- removing approximately located markets gives 28.7%;
- the high-cost scenario gives 24.4%;
- opportunities persist to the next report 79–84% of the time;
- 5 random cases reproduce exactly from raw rows.

What it does not include: spoilage, payment delays and the farmer's relationship with the commission agent. So it is an upper bound on what is practically capturable.

**4. "Your crash model has a PR-AUC of 0.75. Why do you headline 0.29?"**
Because 73.8% of the labelled crashes were already under way on the day of the label. The price was already below 90% of its usual level, so flagging those days is easy and isn't foresight. A farmer needs a warning *before* the fall. On those days the model scores 0.29 against 0.15 for a seasonal calendar (0.25 vs 0.07 outside December). About 3 in 10 warnings come true, about 6.6 days ahead. I missed my own 60% precision target, and I say so. A plain logistic regression is almost as good, which tells me the signal is mostly simple momentum.

**5. "How do you know the data is right?"**
I don't assume it is. Four examples:
- I changed the outlier rule because the textbook version would have deleted 24% of real July 2023 tomato prices.
- I dropped Tamil Nadu after finding that most of its rows were retail-like farmer markets and per-kg entries.
- Suspect series are flagged and excluded, not silently deleted.
- When the app's top "price falling now" entry was onion at ₹100/qtl, I traced it to the raw rows. It was a single report with a changed grade, its neighbours were at ₹700–890, and the next report was ₹801. I then added a "verify before acting" badge for exactly that pattern. The next step is cross-checking against CEDA's independent data.
