# Insights brief: mandi prices for tomato, onion and potato

*Mandi Pulse · Maharashtra, Madhya Pradesh, Uttar Pradesh, Gujarat · 2018-01-01 to 2025-10-31 · 1,757,149 market-days from 594 mandis (Agmarknet). Sources for every number are linked.*

## Headline

**A farmer selling at the nearest mandi often leaves money on the table. On a third of market-days, a mandi within 100 km paid more even after transport and fees. The problem is price information and access, not distance.**

## Context

Tomato, onion and potato are the most price-volatile staples in Indian kitchens and farm incomes. Farmers mostly sell where they always sell. Mandis report prices daily to Agmarknet, but that information rarely reaches the farm gate in a usable form. If nearby mandis routinely disagree, better price information alone can raise farm income without any new infrastructure.

## Findings

1. **Nearby mandis disagree, and distance doesn't explain it.**
   - On a typical day, tomato prices at two mandis within 100 km differ by **15.3% (₹200/qtl)**; for onion and potato the gap is 10.5% and 11.1%.
   - The gap is almost the same for mandis 10 km apart as for mandis 90 km apart (14.3% vs 16.0% for tomato).
   - *So what:* the gaps are local price-discovery failures, not transport costs. [q1_spread_by_commodity](../analysis/queries/phase3/q1_spread_by_commodity.sql), [q1_gap_by_distance](../analysis/queries/phase3/q1_gap_by_distance.sql)
2. **Selling elsewhere pays often, by a meaningful amount, and the signal lasts.**
   - Costs: ₹1.5/qtl/km freight, ₹50/qtl handling and 6% commission and market fees.
   - At least one nearby mandi paid more on **33.8% of market-days**. The robust range is 24.4% (same variety only) to 33.9%; 24.4–42.2% across cost scenarios.
   - The median gain was **₹370/qtl**.
   - When a destination paid more, it still did at the next report **79–84%** of the time.
   - *So what:* a weekly price alert would be actionable, not just noise. [q2_opportunity_rate](tables/phase3/q2_opportunity_rate.csv), [robustness](tables/phase3/robustness.csv), [sanity_05](tables/phase3/sanity_05_actionable_opportunities.csv)
3. **Crashes are seasonal, and some can be anticipated.**
   - December starts a crash on **58% of tomato market-days** (onion 36%, potato 34%).
   - On days *before* a fall begins, a simple model flags crash risk about **twice as well as the seasonal calendar** (PR-AUC 0.29 vs 0.15). About **3 in 10 warnings come true, ~6.6 days ahead**.
   - *So what:* there is a usable but imperfect warning window for timing sales or storage. [q3_seasonality_by_month](tables/phase3/q3_seasonality_by_month.csv), [crash model metrics](ml/crash_risk_metrics.json)

**Structural gap:** 22 districts are **price-trapped**: at most 2 market towns within 50 km, and prices below 90% of the state level. Most are in Madhya Pradesh (15 district-crop cases) and Maharashtra (9), and none are in Uttar Pradesh. The worst is Junagarh onion at 0.53× the state price. [q4_trapped_summary](tables/phase3/q4_trapped_summary.csv)

## Recommendations

**For farmers and FPOs (Farmer Producer Organisations)**
1. **Check two or three mandis within 100 km before every sale, not just the usual one.** An FPO can do this for its members with a daily price message: on a third of days it is worth moving the load. The [Best Mandi](../app/pages/1_Best_Mandi.py) page does this calculation, including fees.
2. **Plan around December (and January for tomato).** Use storage or staggered harvests for onion and potato where possible. Treat a crash warning as a reason to sell or check prices early, not as a certainty.

**For policymakers and APMC boards**
1. **Target the 22 price-trapped districts first.** Options: a collection centre, aggregation by FPOs, or better road links to the nearest well-priced mandi. In trapped onion districts, a better price already exists within 100 km on 62% of market-days, so access is the bottleneck.
2. **Fix the information supply:**
   - restore daily reporting density, which fell from about 25 to under 7 report days a month after the Nov-2025 portal change;
   - publish prices by variety and grade;
   - validate obviously wrong entries at source. The top "falling now" price in our data, onion at ₹100/qtl, was a data-entry artefact.

## Caveats

- **Prices:** modal prices are wholesale indicators per market-day, not what an individual farmer receives. Grades and varieties are mixed; comparing the same variety only lowers the opportunity rate by about a third.
- **Costs:** transport is estimated as straight-line distance × 1.3 × a flat rate, plus 4–8% fees. Spoilage, payment terms and commission-agent ties are not modelled. 23.9% of mandis are located only at their district centre.
- **Coverage:** the analysis ends on 31 Oct 2025. Results are from historical data, and the crash model misses about 6 in 10 crashes on not-yet-falling days.
