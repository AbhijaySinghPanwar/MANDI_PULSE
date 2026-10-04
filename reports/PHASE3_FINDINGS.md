# Phase 3 findings: Q1–Q5

**Scope:** wholesale modal prices (₹ per quintal) for tomato, onion and potato in Maharashtra, Madhya Pradesh, Uttar Pradesh and Gujarat. Main period **2018-01-01 to 2025-10-31**. Only valid rows are used, with suspect-low series excluded unless stated (1,757,149 market × crop × days).

**Every number links to the saved query that produced it.** Each query's output is in [`reports/tables/phase3/`](tables/phase3/).

**Robustness:** each headline is shown as a range over three versions ([`robustness.sql`](../analysis/queries/phase3/robustness.sql) → [`robustness.csv`](tables/phase3/robustness.csv)):
- **(a)** the default;
- **(b)** without any district-centroid geocodes;
- **(c)** with suspect-low series included;
- **(d)** Q2 only: same-variety comparisons.

---

## Q1. How big is the same-day price gap between nearby mandis?

On a typical day, two markets within 100 km (road estimate) quote prices that differ by **10.5% for onion (₹150/qtl), 11.1% for potato (₹100/qtl) and 15.3% for tomato (₹200/qtl)**, measured as a share of the lower price ([q1_spread_by_commodity](../analysis/queries/phase3/q1_spread_by_commodity.sql)). Gaps are often large: on **33–43% of pair-days the gap is 20% or more**, and the worst 10% of days exceed 55–77%. The gap barely depends on distance. Tomato goes from 14.3% for markets 0–20 km apart to 16.0% at 80–100 km ([q1_gap_by_distance](../analysis/queries/phase3/q1_gap_by_distance.sql)), so the gaps are local price differences, not distance effects.

*Robustness (median gap):* onion 10.5–10.6%, potato 10.1–11.1%, tomato 15.2–15.4% across versions a/b/c.
*Figures:* `reports/figures/q1_gap_by_distance.png`, `q1_gap_monthly.png`.

## Q2. After transport costs and fees, how often is a farther mandi actually more profitable?

Costs are the **mid scenario**: transport at ₹1.5 per quintal per km plus ₹50 handling, and **6% commission and market fees** on the destination price. An opportunity needs at least ₹100/qtl and 5% more than selling at home. Two rates answer different questions ([q2_opportunity_rate](../analysis/queries/phase3/q2_opportunity_rate.sql)):

- **At least one nearby mandi paid more after costs on 33.8% of market-days** (tomato 43.2%, onion 33.4%, potato 24.9%).
- **Any single neighbour paid more on 11.9% of days** (tomato 15.4%, onion 12.0%, potato 9.0%).
- **The difference:** a market has on average 8.2 neighbours reporting the same day, so even though each one is rarely better, at least one of them often is.

Across cost scenarios (low: 4% fees, high: 8% fees) the market-day rate is **24.4–42.2%**. When an opportunity exists, the median best gain is **₹370/qtl** (potato ₹278, onion ₹372, tomato ₹451).

*Robustness (mid, all crops):*

| Version | At least one nearby mandi | Any single neighbour |
|---|---|---|
| (a) default | 33.8% | 11.9% |
| (b) no district-centroid pairs | 28.7% | 11.8% |
| (c) incl. suspect-low | 33.9% | 12.0% |
| **(d) same variety only** | **24.4%** | **10.3%** |

Comparing only the same named variety on the same day cuts the market-day rate by about a third. Potato is the most affected (24.9% → 14.9%); tomato goes 43.2% → 29.8% and onion 33.4% → 28.4%. Part of the default rate is a quality/variety difference, not a missed opportunity ([robustness](../analysis/queries/phase3/robustness.sql)).

*Figures:* `q2_opportunity_rate_by_scenario.png`, `q2_gain_distribution.png`.

**How to read this (sanity checks):**
- **Opportunities persist; they are not one-day noise.** When a destination was profitable on the previous comparison day (≤ 3 days earlier), it is profitable again **79–84%** of the time, with a realised median gain of ₹225–314/qtl ([sanity_05](../analysis/queries/phase3/sanity_05_actionable_opportunities.sql)). They come in multi-day episodes: 67% of opportunity days come from pairs profitable on fewer than 40% of their days ([sanity_04](../analysis/queries/phase3/sanity_04_structural_vs_sporadic.sql)).
- **Destinations are concentrated.** The top 20% of destination markets take 67% of opportunities ([sanity_02](../analysis/queries/phase3/sanity_02_opportunity_concentration.sql)). The top ones are western Uttar Pradesh markets on the edge of Delhi NCR, such as Ghaziabad, Muzaffarnagar and Meerut ([sanity_03](../analysis/queries/phase3/sanity_03_top_destinations.sql)).
- **The rate is not one state or one year:** 22–49% across state × crop ([sanity_07](../analysis/queries/phase3/sanity_07_opportunity_by_state.sql)), and 21–54% across crop-years ([q2_opportunity_by_year](../analysis/queries/phase3/q2_opportunity_by_year.sql)).
- **Spoilage in transit is not modelled.** Fees are charged only at the destination, which is conservative: selling at home costs fees too.
- **Spot-check:** 5 random opportunities reproduce exactly from the raw rows ([sanity_08](../analysis/queries/phase3/sanity_08_spotcheck_opportunities.sql); details in PROGRESS.md).

## Q3. Which months and crops crash predictably? How early do warning signs appear?

The seasonal pattern is strong and repeats ([q3_seasonality_by_month](../analysis/queries/phase3/q3_seasonality_by_month.sql)):
- **Tomato** prices peak in **July (1.79× the annual median)** and again in October, and bottom out in February–April (about 0.67–0.70×).
- **Onion** peaks in **November (1.66×)** and is cheapest in April–May (about 0.71–0.73×).
- **Potato** is flatter (0.76–1.20×).

**Crash definition (decision 2026-10-04):** on **at least 2 report days** within the next 14, the price is below 70% of its trailing 30-day median.

**December is the crash month for all three crops.** Its share of market-days that start a crash: **tomato 58%, onion 36%, potato 34%**. Tomato also crashes in January (36%) and in August–September (34%, 30%) after its July spike; onion crashes in March (31%).

Across all months the crash rate is **tomato 21.4%, onion 11.7%, potato 6.0%**. Under the original single-quote rule the rates were 26.0%, 15.4% and 8.0%. December is the peak under every definition ([sanity_09](../analysis/queries/phase3/sanity_09_crash_definition.sql)).

**Warning signs:** on crash-labelled days the price is typically *already* at about **76–79% of its 30-day median**, versus about 100% on other days ([q3_crash_lead](../analysis/queries/phase3/q3_crash_lead.sql)). Part of each fall is visible before the window starts; the Phase 4 crash model measures how much warning is really possible.

*Robustness (crash rate):* tomato 21.44–21.77%, onion 11.74–12.21%, potato 6.00–6.14%; December is the peak month in all versions.
*Figures:* `q3_price_index_by_month.png`, `q3_crash_rate_heatmap.png`.

## Q4. Which districts are "price-trapped"?

**29 district × crop combinations in 22 districts** are price-trapped, out of 463 district × crop combinations ([q4_trapped_summary](../analysis/queries/phase3/q4_trapped_summary.sql)). Price-trapped means at most 2 town locations with data within 50 km, *and* prices on average below 90% of the state's on the same days.
- They are concentrated in **Madhya Pradesh (15), Maharashtra (9) and Gujarat (5)**. **None are in Uttar Pradesh**, whose market network is much denser.
- The most severe: Junagarh onion (Gujarat) at 0.53× the state price, Guna potato (MP) 0.58×, Guna tomato 0.60× and Jalna potato (MH) 0.63× ([q4_district_access](../analysis/queries/phase3/q4_district_access.sql)).
- Trapped onion districts more often have a profitable market within 100 km after costs (62% of market-days vs 32% elsewhere). The better price exists nearby; the gap is in access or information.

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
- Costs cover per-km freight, a fixed handling cost and 4–8% commission/market fees (which vary by state). Spoilage is not included.
- The period ends on 2025-10-31; data after the Nov-2025 source change is excluded (see `docs/DATA_SOURCES.md`).
