# Phase 3 findings: Q1–Q5

**Scope:** wholesale modal prices (₹ per quintal) for tomato, onion and potato in Maharashtra, Madhya Pradesh, Uttar Pradesh and Gujarat. Main period **2018-01-01 to 2025-10-31**. Only valid rows are used, with suspect-low series excluded unless stated (1,757,149 market × crop × days).

**Every number links to the saved query that produced it.** Each query's output is in [`reports/tables/phase3/`](tables/phase3/).

**Robustness:** each headline is shown as a range over three versions ([`robustness.sql`](../analysis/queries/phase3/robustness.sql) → [`robustness.csv`](tables/phase3/robustness.csv)):
- **(a)** the default;
- **(b)** without any district-centroid geocodes;
- **(c)** with suspect-low series included.

---

## Q1. How big is the same-day price gap between nearby mandis?

On a typical day, two markets within 100 km (road estimate) quote prices that differ by **10.5% for onion (₹150/qtl), 11.1% for potato (₹100/qtl) and 15.3% for tomato (₹200/qtl)**, measured as a share of the lower price ([q1_spread_by_commodity](../analysis/queries/phase3/q1_spread_by_commodity.sql)). Gaps are often large: on **33–43% of pair-days the gap is 20% or more**, and the worst 10% of days exceed 55–77%. The gap barely depends on distance. Tomato goes from 14.3% for markets 0–20 km apart to 16.0% at 80–100 km ([q1_gap_by_distance](../analysis/queries/phase3/q1_gap_by_distance.sql)), so the gaps are local price differences, not distance effects.

*Robustness (median gap):* onion 10.5–10.6%, potato 10.1–11.1%, tomato 15.2–15.4% across versions a/b/c.
*Figures:* `reports/figures/q1_gap_by_distance.png`, `q1_gap_monthly.png`.

## Q2. After transport costs, how often is a farther mandi actually more profitable?

Under the **mid cost scenario** (₹1.5 per qtl per km + ₹50), on **43.9% of market-days** at least one market within 100 km paid at least ₹100/qtl and 5% more, net of transport ([q2_opportunity_rate](../analysis/queries/phase3/q2_opportunity_rate.sql)). By crop: **tomato 53.2%, onion 44.8%, potato 33.5%**. Across the low and high cost scenarios the overall rate ranges from **35.0% to 49.9%**. When such a move exists, the median best gain is **₹383/qtl** (potato ₹290, onion ₹381, tomato ₹473).

*Robustness (mid rate, all crops):* 37.9% (b, no centroid pairs) to 44.0% (c, incl. suspect-low); 43.9% default.
*Figures:* `q2_opportunity_rate_by_scenario.png`, `q2_gain_distribution.png`.

**How to read this (sanity checks; the rate exceeded 50% for tomato, so it was investigated):**
- **It is "best of ~8 neighbours".** A market has on average 8.2 neighbours reporting the same day. Any *one specific* neighbour is profitable on only **12.6–20.5%** of comparisons (mid; [q2_opportunity_rate](../analysis/queries/phase3/q2_opportunity_rate.sql)).
- **It is mostly not random noise.** When a destination was profitable on the previous comparison day (≤ 3 days earlier), it is profitable again **80–85%** of the time, with a realised median gain of ₹238–321/qtl ([sanity_05](../analysis/queries/phase3/sanity_05_actionable_opportunities.sql)). Gaps come in multi-day episodes: 61% of opportunity days come from pairs that are profitable on fewer than 40% of their days ([sanity_04](../analysis/queries/phase3/sanity_04_structural_vs_sporadic.sql)).
- **The best destinations are concentrated.** The top 20% of destination markets take 66% of opportunities ([sanity_02](../analysis/queries/phase3/sanity_02_opportunity_concentration.sql)). The top 15 are all western Uttar Pradesh markets on the edge of Delhi NCR, such as Ghaziabad, Meerut and Muzaffarnagar ([sanity_03](../analysis/queries/phase3/sanity_03_top_destinations.sql)).
- **Variety mix inflates onion and potato.** Pairs whose dominant varieties differ show more opportunities (onion 24.7% vs 15.3% for same-variety pairs; potato 14.3% vs 10.8%). Tomato shows no difference ([sanity_06](../analysis/queries/phase3/sanity_06_variety_mix.sql)).
- **The rate is not driven by one state:** 31–55% in every state × crop ([sanity_07](../analysis/queries/phase3/sanity_07_opportunity_by_state.sql)). It is stable over the years: 29–64% per crop-year ([q2_opportunity_by_year](../analysis/queries/phase3/q2_opportunity_by_year.sql)).
- **Costs not modelled:** commission (*aadhat*), market fees and spoilage are excluded, so the true profitable share is lower than shown.
- **Spot-check:** 5 randomly chosen opportunities reproduce exactly from the raw rows ([sanity_08](../analysis/queries/phase3/sanity_08_spotcheck_opportunities.sql); details in PROGRESS.md).

## Q3. Which months and crops crash predictably? How early do warning signs appear?

The seasonal pattern is strong and repeats ([q3_seasonality_by_month](../analysis/queries/phase3/q3_seasonality_by_month.sql)):
- **Tomato** prices peak in **July (1.79× the annual median)** and again in October, and bottom out in February–April (about 0.67–0.70×).
- **Onion** peaks in **November (1.66×)** and is cheapest in April–May (about 0.71–0.73×).
- **Potato** is flatter (0.76–1.20×).

**December is the crash month for all three crops.** A crash is defined (spec 9.2) as the price falling below 70% of its 30-day median within the next 14 days. Its share of market-days in December: **tomato 64%, onion 42%, potato 39%**. Tomato also crashes in August–September (40%, 34%) after its July spike, and onion in March (36%).

Across all months the crash rate is **tomato 26.0%, onion 15.4%, potato 8.0%**. These are mostly genuine seasonal falls rather than noise from single low quotes: requiring the fall on ≥ 2 days still gives tomato 21.4%, and December remains the peak under every definition ([sanity_09](../analysis/queries/phase3/sanity_09_crash_definition.sql)).

**Warning signs:** on days labelled as crashes, the price is *already* at about **80% of its 30-day median**, versus about 100% on other days ([q3_crash_lead](../analysis/queries/phase3/q3_crash_lead.sql)). Part of each fall is visible before the window starts; Phase 4 will measure this properly.

*Robustness (crash rate):* tomato 25.97–26.52%, onion 15.42–16.08%, potato 8.01–8.35%; December is the peak month in all versions.
*Figures:* `q3_price_index_by_month.png`, `q3_crash_rate_heatmap.png`.

## Q4. Which districts are "price-trapped"?

**29 district × crop combinations in 22 districts** are price-trapped, out of 463 district × crop combinations ([q4_trapped_summary](../analysis/queries/phase3/q4_trapped_summary.sql)). Price-trapped means at most 2 town locations with data within 50 km, *and* prices on average below 90% of the state's on the same days.
- They are concentrated in **Madhya Pradesh (15), Maharashtra (9) and Gujarat (5)**. **None are in Uttar Pradesh**, whose market network is much denser.
- The most severe: Junagarh onion (Gujarat) at 0.53× the state price, Guna potato (MP) 0.58×, Guna tomato 0.60× and Jalna potato (MH) 0.63× ([q4_district_access](../analysis/queries/phase3/q4_district_access.sql)).
- Trapped onion districts more often have a profitable market within 100 km (67% of market-days vs 41% elsewhere). The better price exists nearby; the gap is in access or information.

*Robustness:* 22 trapped districts (a, c) to 26 (b, counting only market-level geocodes as nearby towns).
*Figure:* `q4_district_access_scatter.png`.

## Q5. How does volatility differ between the perishable (tomato) and storables (onion, potato)?

**Tomato is the most volatile and potato the least** ([q5_volatility_by_commodity](../analysis/queries/phase3/q5_volatility_by_commodity.sql)):

| Measure (median per market-year) | Tomato | Onion | Potato |
|---|---|---|---|
| Coefficient of variation | **0.49** | 0.39 | 0.25 |
| Average day-to-day price change | **5.6%** | 4.7% | 2.7% |
| Largest within-year fall | **74%** | 67% | 53% |

The ranking is not fixed, though. Tomato is the most volatile in 6 of 8 years, but **onion was more volatile in 2019 and 2020**, the onion-crisis years. Potato is the least volatile in 7 of 8 years and tied with onion in 2022 ([q5_volatility_by_year](../analysis/queries/phase3/q5_volatility_by_year.sql)).

*Robustness (median CV):* tomato 0.491–0.494, onion 0.394–0.401, potato 0.248–0.249.
*Figures:* `q5_volatility_by_commodity.png`, `q5_cv_by_year.png`.

---

### Caveats
- Modal price is a wholesale indicator for a market-day, not what an individual farmer receives, and it mixes varieties and grades.
- Road distance is estimated as straight-line distance × 1.3. 23.9% of markets are located only at their district centroid; version (b) of the robustness checks shows the effect.
- Transport cost covers per-km freight plus a fixed handling cost only. Commission, market fees and spoilage are not included.
- The period ends on 2025-10-31; data after the Nov-2025 source change is excluded (see `docs/DATA_SOURCES.md`).
