# ML report: forecast, crash warning, market segments (Phase 4)

**Data:** `fact_daily_price`, main period 2018-01-01 to 2025-10-31, valid rows only, suspect-low series excluded. One real report per market × crop × day; prices are in ₹ per quintal.

**How the numbers are produced.** Every number in this report is generated from the saved metrics files in [`reports/ml/`](ml/) (`price_forecast_metrics.json`, `crash_risk_metrics.json`, `market_cluster_metrics.json`, `shap_*.json`) by `python -m mandipulse ml report`. Re-running `python -m mandipulse ml train-all` reproduces them (fixed seed 42).

**Leakage rules:**
- Every feature at day *t* uses only data up to *t*; state-level features use *t − 1*.
- Forward-filling (≤ 3 days) is used for features only.
- Targets are always real reports: a day with no report has no target.

These rules are enforced by `tests/test_features_no_leakage.py`.

---

## Model A: 7-day price forecast

**Setup**
- **Model:** one global LightGBM on the 7-day log price change, with quantile models at 0.1 / 0.5 / 0.9. The p50 is the point forecast.
- **Features (spec 9.1 plus your additions):** lags, rolling statistics, momentum, year-on-year change, days since the last report, report days in the last 30, the previous day's state median and its 7-day change, the number of markets reporting in the state, calendar, crop, state and market.
- **Validation:** walk-forward by target month, May–Oct 2025. Each month is trained only on targets dated before it.

### Result: the model beats the best baseline (Last value) by 6.9% on MAE. That is below the spec's 10% target.

| Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|
| **LightGBM (p50)** | 108004 | 147.6 | 9.77 | 9.27 |
| Last value | 108004 | 158.6 | 10.31 | 10.03 |
| Value 7 days ago | 108004 | 220.7 | 13.67 | 13.45 |
| 7-day moving average | 108004 | 172.4 | 10.85 | 10.6 |

- The **first run** used a squared-error objective. It estimates the mean, but MAE rewards the median, and it was only 1.2% better than "last value" (MAE ₹156.7). Switching the p50 to a median (quantile 0.5) objective gave the result above.
- Both runs are kept: [`attempts/price_forecast_metrics_run1_l2_objective.json`](ml/attempts/price_forecast_metrics_run1_l2_objective.json).
- No other tuning was done on the test months.

**By crop.** The model beats "last value" for every crop. Tomato gains most: ₹292.5 vs ₹318.9. Onion is ₹92.7 vs ₹95.7, potato ₹56.7 vs ₹60.4.

| Crop | Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|---|
| all | **LightGBM (p50)** | 108004 | 147.6 | 9.77 | 9.27 |
| all | Last value | 108004 | 158.6 | 10.31 | 10.03 |
| all | Value 7 days ago | 108004 | 220.7 | 13.67 | 13.45 |
| all | 7-day moving average | 108004 | 172.4 | 10.85 | 10.6 |
| Onion | **LightGBM (p50)** | 38796 | 92.7 | 9.1 | 8.35 |
| Onion | Last value | 38796 | 95.7 | 9.3 | 8.76 |
| Onion | Value 7 days ago | 38796 | 120.8 | 11.38 | 10.76 |
| Onion | 7-day moving average | 38796 | 95.7 | 9.15 | 8.63 |
| Potato | **LightGBM (p50)** | 33481 | 56.7 | 4.78 | 4.68 |
| Potato | Last value | 33481 | 60.4 | 5.05 | 4.97 |
| Potato | Value 7 days ago | 33481 | 72.9 | 6.14 | 6.04 |
| Potato | 7-day moving average | 33481 | 59.7 | 5.02 | 4.95 |
| Tomato | **LightGBM (p50)** | 35727 | 292.5 | 15.17 | 14.57 |
| Tomato | Last value | 35727 | 318.9 | 16.33 | 16.14 |
| Tomato | Value 7 days ago | 35727 | 467.8 | 23.21 | 23.31 |
| Tomato | 7-day moving average | 35727 | 361.3 | 18.17 | 18.05 |

**By reporting segment.** Frequent reporters (≥ 15 report days in the prior 30) vs sparse reporters:

| Segment | Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|---|
| all | **LightGBM (p50)** | 108004 | 147.6 | 9.77 | 9.27 |
| all | Last value | 108004 | 158.6 | 10.31 | 10.03 |
| all | Value 7 days ago | 108004 | 220.7 | 13.67 | 13.45 |
| all | 7-day moving average | 108004 | 172.4 | 10.85 | 10.6 |
| frequent | **LightGBM (p50)** | 100429 | 145.5 | 9.43 | 8.99 |
| frequent | Last value | 100429 | 156.5 | 9.97 | 9.73 |
| frequent | Value 7 days ago | 100429 | 220.9 | 13.4 | 13.24 |
| frequent | 7-day moving average | 100429 | 171.2 | 10.56 | 10.36 |
| sparse | **LightGBM (p50)** | 7575 | 175.6 | 14.24 | 13.06 |
| sparse | Last value | 7575 | 186.9 | 14.76 | 13.96 |
| sparse | Value 7 days ago | 7575 | 218.6 | 17.16 | 16.18 |
| sparse | 7-day moving average | 7575 | 188.1 | 14.76 | 13.82 |

Sparse reporters are harder for every method (MAE ₹175.6 vs ₹145.5 for the model). The model's advantage holds in both segments (sparse: ₹175.6 vs ₹186.9 for "last value").

**By test month:**

| Test month | Rows | MAE (Rs/qtl) | MAPE % |
|---|---|---|---|
| 2025-05 | 19744 | 93.6 | 8.68 |
| 2025-06 | 19249 | 147.9 | 10.74 |
| 2025-07 | 20265 | 174.0 | 9.67 |
| 2025-08 | 19097 | 183.1 | 9.34 |
| 2025-09 | 17497 | 154.8 | 10.85 |
| 2025-10 | 12152 | 125.1 | 9.24 |

**Prediction band (raw, before calibration):** p10–p90 coverage is all 75.6%, frequent 75.5%, sparse 77.6%, against a target of about 80%. The calibration below fixes most of the gap.

### Was the median objective chosen fairly? Check on a pre-test validation window

The switch from the L2 (mean) to the L1 (median) objective was made *after* seeing the test-month results. To validate it independently, both objectives were re-run as a walk-forward on **Nov 2024 – Apr 2025**, using only targets dated **before 2025-05-01**, i.e. no test-month data at all (`python -m mandipulse ml validate-forecast`, [`forecast_validation_metrics.json`](ml/forecast_validation_metrics.json)):

| Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|
| **LightGBM, median (L1) objective** | 104950 | 167.6 | 10.37 | 9.81 |
| LightGBM, mean (L2) objective | 104950 | 175.5 | 10.58 | 10.22 |
| Last value | 104950 | 196.6 | 12.27 | 11.18 |
| Value 7 days ago | 104950 | 293.4 | 18.44 | 15.97 |
| 7-day moving average | 104950 | 223.3 | 13.98 | 12.48 |

By validation month (MAE, ₹/qtl):

| Validation month | L1 MAE | L2 MAE | Last value MAE |
|---|---|---|---|
| 2024-11 | 232.4 | 249.5 | 258.8 |
| 2024-12 | 287.1 | 310.2 | 337.0 |
| 2025-01 | 162.5 | 162.9 | 205.9 |
| 2025-02 | 131.6 | 136.1 | 144.6 |
| 2025-03 | 113.2 | 116.6 | 132.3 |
| 2025-04 | 91.7 | 92.5 | 113.1 |

- **Winner on validation: L1 (median).** L1 vs L2: 4.5% lower MAE.
- Against the best baseline on validation: L1 is 14.8% better and L2 is 10.7% better.

**The median (L1) objective also wins on the pre-test validation window, so the choice is justified without using the test months.**

### Prediction band calibration (p10–p90)

The raw quantile band was too narrow. It was widened with a simple conformal (CQR-style) correction fitted **only on the validation window above**:
- score per row = how far the actual price fell outside the band, in log terms;
- the three quantile models are fitted separately, so on a few rows the band edges cross the median; they are clipped to it (p10 ≤ p50 ≤ p90, the median itself unchanged);
- per crop, the band is widened by the score quantile that gives 80% coverage on validation (log widening: Onion 0.011, Potato -0.004, Tomato 0.007).

Validation coverage went from 78.6% to 80.0%. On the untouched test months it went from **75.6% to 77.3%**; the median band width went from 20.6% to 21.7% of the forecast.

| Window | Slice | Coverage before % | Coverage after % |
|---|---|---|---|
| Test months May-Oct 2025 | all | 75.6 | 77.3 |
| Test months May-Oct 2025 | segment: frequent | 75.5 | 77.1 |
| Test months May-Oct 2025 | segment: sparse | 77.6 | 78.8 |
| Test months May-Oct 2025 | Onion | 76.9 | 82.4 |
| Test months May-Oct 2025 | Potato | 77.3 | 73.8 |
| Test months May-Oct 2025 | Tomato | 72.7 | 74.9 |
| Stress test Jul-Aug 2023 | all | 66.5 | 67.6 |
| Stress test Jul-Aug 2023 | segment: frequent | 67.4 | 68.5 |
| Stress test Jul-Aug 2023 | segment: sparse | 57.1 | 57.8 |
| Stress test Jul-Aug 2023 | Onion | 69.9 | 74.6 |
| Stress test Jul-Aug 2023 | Potato | 79.0 | 75.5 |
| Stress test Jul-Aug 2023 | Tomato | 43.4 | 45.6 |

Caveats: the gain is small, and calibration is not uniform. Potato already had about 80% coverage on validation, so its band was slightly *narrowed*, and its test coverage fell. I did not change the method after seeing this, because that would be tuning on the test months again. Shocks (the 2023 tomato spike) stay far below 80% whatever the calibration.

The served forecasts (`ml.price_forecast`, `ml.price_forecast_backtest`, the app) use the calibrated band.

### Stress test: July–August 2023 tomato spike

The model was trained only on targets before 2023-07-01 and evaluated on July–August 2023. Overall it beats the best baseline by 3.6% on MAE:

| Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|
| **LightGBM (p50)** | 34998 | 402.0 | 11.87 | 11.94 |
| Last value | 34998 | 416.9 | 13.15 | 12.8 |
| Value 7 days ago | 34998 | 684.9 | 20.42 | 20.64 |
| 7-day moving average | 34998 | 519.9 | 15.77 | 15.5 |

Tomato only (the spike):

| Model | Rows | MAE (Rs/qtl) | MAPE % | sMAPE % |
|---|---|---|---|---|
| **LightGBM (p50)** | 8783 | 1316.1 | 26.16 | 25.95 |
| Last value | 8783 | 1353.7 | 29.66 | 27.52 |
| Value 7 days ago | 8783 | 2287.1 | 49.86 | 48.36 |
| 7-day moving average | 8783 | 1727.2 | 37.98 | 35.68 |

**What happened** (`reports/figures/ml_stress_test_tomato_jul2023.png`, three Uttar Pradesh markets):
- **The rise:** every method lagged the sudden rise in early July (prices went from about ₹1,000 to ₹7,000+ in two weeks). A 7-day-ahead model cannot see a shock that has not started.
- **The plateau:** the model sat about 10% *below* the high plateau. It "expects" reversion.
- **The fall:** it turned down several days earlier than "last value" in the mid-August collapse.
- **Overall:** the error is large for everyone (tomato MAE ₹1316.1 vs ₹1353.7 for "last value"), and band coverage fell to all 66.5%, frequent 67.4%, sparse 57.1%.

**Honest takeaway:** a useful but modest improvement in normal times; no magic in a shock.

---

## Model B: crash early warning

### Headline: on days when the price has *not yet* started falling, the model ranks crash risk about twice as well as the seasonal rule, and more than three times as well outside December. About 3 in 10 of its early warnings come true, around a week ahead.

**Why this is the headline.** 73.8% of labelled crashes occur when the price is *already* below 90% of its trailing 30-day median on the day of the label. The fall has already begun, so flagging those days is easy and inflates any "all days" metric. The useful question for a farmer is whether the model can warn **before** the fall. So the headline is measured only on days when the price was still ≥ 90% of its median:

Rows: 690,477; crash days: 28,231 (prevalence 4.09%).

| Model | PR-AUC | Lift over prevalence | Precision % | Recall % | Alerts | Avg lead (days) |
|---|---|---|---|---|---|---|
| Prevalence (base rate) | 0.0417 | 1.02 | – | 0.0 | 0 | – |
| Seasonal rule (crop x month) | 0.1465 | 3.58 | 18.4 | 22.5 | 34487 | 7.6 |
| Logistic regression | 0.2833 | 6.93 | 31.0 | 35.0 | 31804 | 6.4 |
| **LightGBM** | 0.2929 | 7.16 | 30.1 | 37.6 | 35296 | 6.6 |

**Same, excluding December** (where crashes are seasonal and easy to anticipate):

Rows: 661,045; crash days: 21,720 (prevalence 3.29%).

| Model | PR-AUC | Lift over prevalence | Precision % | Recall % | Alerts | Avg lead (days) |
|---|---|---|---|---|---|---|
| Prevalence (base rate) | 0.0338 | 1.03 | – | 0.0 | 0 | – |
| Seasonal rule (crop x month) | 0.0744 | 2.27 | 9.2 | 7.1 | 16636 | 7.6 |
| Logistic regression | 0.2397 | 7.29 | 27.8 | 26.0 | 20366 | 5.8 |
| **LightGBM** | 0.2538 | 7.72 | 27.3 | 30.3 | 24094 | 6.2 |

- PR-AUC **0.2929** vs **0.1465** for the seasonal rule. Outside December: **0.2538** vs **0.0744**, which is 7.72× the base rate of 3.29%.
- At the validated alert threshold: precision **30.1%**, recall 37.6%. The precision ≥ 0.6 target is **not** met for genuine early warnings.
- Correct early warnings arrive on average **6.6 days** before the first low report.

**Setup**
- **Label (decision 2026-10-04):** a crash at day *t* means that on ≥ 2 report days in the next 14, the price is below 70% of its trailing 30-day median. Labels exist only for real report days.
- **Features:** Model A's features plus 7/14-day slopes, the previous day's state share of falling markets, and the historical crash rate for the crop × month (training data only).
- **Validation (deviation from the May–Oct 2025 window, which has no December):** yearly expanding folds, with test years 2022, 2023, 2024 and Jan–Oct 2025. For each test year the alert threshold is chosen on the *previous* year, by a model that never saw that year, targeting precision ≥ 0.6.

| Test year | LightGBM threshold | Reached precision >= 0.6 on validation year? |
|---|---|---|
| 2022 | 0.6308 | yes |
| 2023 | 0.6532 | yes |
| 2024 | 0.4985 | yes |
| 2025 | 0.8043 | yes |

### All days (flattering: most of these "crashes" are already under way)

Rows: 868,648; crash days: 107,897 (prevalence 12.42%).

| Model | PR-AUC | Lift over prevalence | Precision % | Recall % | Alerts | Avg lead (days) |
|---|---|---|---|---|---|---|
| Prevalence (base rate) | 0.1259 | 1.01 | – | 0.0 | 0 | – |
| Seasonal rule (crop x month) | 0.341 | 2.75 | 39.8 | 22.8 | 61769 | 4.4 |
| Logistic regression | 0.7295 | 5.87 | 57.7 | 73.5 | 137354 | 3.8 |
| **LightGBM** | 0.7483 | 6.02 | 57.5 | 73.0 | 136948 | 3.8 |

**December:**

Rows: 58,124; crash days: 25,292 (prevalence 43.51%).

| Model | PR-AUC | Lift over prevalence | Precision % | Recall % | Alerts | Avg lead (days) |
|---|---|---|---|---|---|---|
| Prevalence (base rate) | 0.3895 | 0.9 | – | 0.0 | 0 | – |
| Seasonal rule (crop x month) | 0.5617 | 1.29 | 50.2 | 75.9 | 38243 | 4.6 |
| Logistic regression | 0.821 | 1.89 | 60.1 | 89.9 | 37829 | 4.5 |
| **LightGBM** | 0.8237 | 1.89 | 62.2 | 86.0 | 34975 | 4.5 |

**Other months:**

Rows: 810,524; crash days: 82,605 (prevalence 10.19%).

| Model | PR-AUC | Lift over prevalence | Precision % | Recall % | Alerts | Avg lead (days) |
|---|---|---|---|---|---|---|
| Prevalence (base rate) | 0.1036 | 1.02 | – | 0.0 | 0 | – |
| Seasonal rule (crop x month) | 0.2308 | 2.26 | 22.8 | 6.5 | 23526 | 3.9 |
| Logistic regression | 0.697 | 6.84 | 56.8 | 68.4 | 99525 | 3.5 |
| **LightGBM** | 0.7224 | 7.09 | 55.9 | 69.0 | 101973 | 3.6 |

The all-days precision of 57.5% and recall of 73.0% look strong. Most of that comes from recognising falls that have already started (those days have a crash rate above 40%), not from foresight.

### Verdict

| Segment | LightGBM PR-AUC | Seasonal rule PR-AUC | Logistic PR-AUC | Beats seasonal rule? | Gain vs seasonal |
|---|---|---|---|---|---|
| all | 0.7483 | 0.341 | 0.7295 | yes | 119.4% |
| december | 0.8237 | 0.5617 | 0.821 | yes | 46.6% |
| other months | 0.7224 | 0.2308 | 0.697 | yes | 213.0% |
| not yet falling | 0.2929 | 0.1465 | 0.2833 | yes | 99.9% |
| not yet falling other months | 0.2538 | 0.0744 | 0.2397 | yes | 241.1% |

- The model beats the seasonal rule in every segment, including on not-yet-falling days outside December.
- In December the seasonal rule alone is strong (PR-AUC 0.5617). The model adds which markets will crash (PR-AUC 0.8237).
- **Logistic regression is almost as good as LightGBM** (PR-AUC 0.2397 vs 0.2538 on the hardest segment). The signal is mostly simple momentum. LightGBM is served; the logistic weights are shown in the app for transparency.

## Model C: market segments

- **Features (per market × crop series with ≥ 180 report days):** price CV, average price index vs the same-day state median, reporting frequency, seasonal amplitude, crash rate, and the number of other town locations within 50 km.
- **Method:** standardised features (log of the town count), KMeans.
- **Data:** clustered on the sensitivity data, so the suspect-low series are included and can be located.
- **Silhouette:** k=3: 0.2275, k=4: 0.2129, k=5: 0.2132, k=6: 0.1923. The scores for k = 3–5 are within 0.02 of each other, so the **most detailed k within 0.02 of the best** was chosen: **k = 5**. Its segments are distinct and nameable; k = 3 merged under-priced and premium markets.

**Cluster profiles** (medians; names come from the centroid z-scores):

| Cluster | Series | CV | Price index | Report freq | Seasonal amp. | Crash rate | Towns ≤50 km | Suspect-low series |
|---|---|---|---|---|---|---|---|---|
| Under-priced, sparse reporting | 164 | 0.475 | 0.899 | 0.378 | 0.89 | 0.096 | 6.0 | 4 |
| Volatile & crash-prone | 309 | 0.646 | 1.018 | 0.722 | 1.348 | 0.209 | 4.0 | 1 |
| Isolated premium market | 134 | 0.441 | 1.19 | 0.478 | 0.742 | 0.093 | 1.0 | 0 |
| Stable, regular market | 425 | 0.448 | 1.004 | 0.776 | 0.754 | 0.071 | 5.0 | 2 |
| Erratic & under-priced, thin reporting | 96 | 0.701 | 0.909 | 0.277 | 2.0 | 0.211 | 4.0 | 11 |

**Where the suspect-low series landed:** of the 18 suspect-low series with enough history, the split is Erratic & under-priced, thin reporting: 11, Under-priced, sparse reporting: 4, Stable, regular market: 2, Volatile & crash-prone: 1. Most fall in the small "Erratic & under-priced, thin reporting" segment: very volatile, very seasonal, rarely reporting and below the state price. That fits the suspicion that their low prices are data problems rather than a real market type. They remain flagged for the CEDA cross-check.

---

## Explainability (SHAP)

- **Method:** exact TreeSHAP (LightGBM `pred_contrib`) on 50,000 sampled rows per model.
- **Plots:** `reports/figures/shap_price_forecast.png` and `shap_crash_risk.png`.
- **Direction column:** the rank correlation between a feature's value and its SHAP value (+ means higher values push the prediction up).

### Model A: top drivers

| Rank | Feature | Mean abs SHAP | Direction (corr. of value with SHAP) |
|---|---|---|---|
| 1 | state_change_7_prev1 | 0.02347 | 0.895 |
| 2 | state_rel_prev1 | 0.01621 | -0.807 |
| 3 | lp_t | 0.01318 | -0.82 |
| 4 | market_key | 0.01166 | – |
| 5 | week_of_year | 0.01121 | 0.328 |
| 6 | roll_mean_7_rel | 0.00598 | 0.481 |
| 7 | month | 0.00361 | 0.074 |
| 8 | commodity | 0.00348 | – |
| 9 | roll_mean_14_rel | 0.00347 | 0.661 |
| 10 | d_lag_1 | 0.00321 | -0.563 |

**Top 5 drivers in plain English:**
1. **Regional momentum** (`state_change_7_prev1`, +): if the state-wide median price rose over the past week (as of yesterday), this market's price is forecast to rise too. Markets move with their region.
2. **Distance from the regional price** (`state_rel_prev1`, −): a market priced above yesterday's state median tends to fall back towards it, and one priced below tends to catch up. Prices converge across nearby markets.
3. **Current price level** (`lp_t`, −): unusually high prices tend to come down and low ones go up (mean reversion).
4. **Which market** (`market_key`): some markets systematically behave differently, e.g. how fast they follow regional moves.
5. **Time of year** (`week_of_year`, +, weaker): the calendar shifts the expected change, e.g. the weeks before a crop's seasonal peak.

### Model B: top drivers

| Rank | Feature | Mean abs SHAP | Direction (corr. of value with SHAP) |
|---|---|---|---|
| 1 | hist_crash_rate | 0.79965 | 0.947 |
| 2 | market_key | 0.58464 | – |
| 3 | roll_mean_30_rel | 0.54684 | 0.814 |
| 4 | momentum_30 | 0.53794 | -0.851 |
| 5 | state_share_falling_prev1 | 0.33787 | 0.955 |
| 6 | state_rel_prev1 | 0.27128 | 0.838 |
| 7 | lp_t | 0.26134 | 0.824 |
| 8 | roll_max_30_rel | 0.18672 | 0.821 |
| 9 | d_lag_14 | 0.16958 | -0.763 |
| 10 | state_change_7_prev1 | 0.16409 | -0.732 |

**Top 5 drivers in plain English:**
1. **Seasonal crash history** (`hist_crash_rate`, +): crop × months that crashed often in the training years (above all December) carry much higher risk.
2. **Which market** (`market_key`): some markets crash far more often than others.
3. **Price below its recent average** (`roll_mean_30_rel`, +): when the 30-day average is well above today's price, the fall has already started and a sustained drop is likely.
4. **Negative momentum** (`momentum_30`, −): the same signal from the other side. The further today's price sits below its 30-day mean, the higher the risk.
5. **Neighbours already falling** (`state_share_falling_prev1`, +): when a large share of the state's markets were already falling yesterday, a local crash becomes much more likely.

---

## How to quote these results

Honest one-sentence claims (each backed by a table above):

1. "I built a 7-day mandi price forecast (LightGBM, walk-forward validated) that cut average error by **6.9%** versus the best simple baseline, 'next week = today', and I checked the model choice on a separate pre-test window."
2. "For crash early warning, on days *before* prices start falling, my model ranked risk about **2× better than a seasonal rule** (PR-AUC 0.2929 vs 0.1465; 0.2538 vs 0.0744 outside December). About **3 in 10 warnings came true**, around **6.6 days ahead**."
3. "I found that 73.8% of labelled 'crashes' were already under way when labelled, so I report the early-warning subset as the headline instead of the flattering all-days score."
4. "I calibrated the forecast's p10–p90 range with a conformal correction fitted on a validation window, raising test coverage from 75.6% to 77.3% (target 80%)."

## Limitations

- **The forecast gain is modest.** 6.9% lower MAE than "last value" is below the 10% target. Day-to-day mandi prices are close to a random walk at a 7-day horizon, and a large share of error comes from sudden shocks (the 2023 tomato spike) that no price-history model can foresee. Weather, arrivals (from CEDA) and policy events would be the next features to try.
- **The raw prediction band was too narrow.** It is now calibrated on a validation window (test coverage 75.6% → 77.3%), but in shocks such as the 2023 tomato spike coverage still drops well below 80%.
- **Crash labels are common and seasonal.** Most labelled crashes are already under way at *t*. Genuine early warnings are possible, with about 6 days' lead, but at roughly 30% precision.
- **Test period:** the walk-forward window (May–Oct 2025) falls in a year when reporting was already thinning. Results for 2025-11 onward, after the source change, are not evaluated.
- **Regional mix:** most rows come from Uttar Pradesh, so metrics are dominated by UP markets.
- **Clusters are descriptive.** Silhouette scores are low (about 0.2), so the segments overlap; they are useful labels, not hard categories.
