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

### Result: the model beats the best baseline ({{a_best_baseline}}) by {{a_improvement}} on MAE. That is below the spec's 10% target.

{{a_overall}}

- The **first run** used a squared-error objective. It estimates the mean, but MAE rewards the median, and it was only {{a_run1_improvement}} better than "last value" (MAE ₹{{a_run1_mae}}). Switching the p50 to a median (quantile 0.5) objective gave the result above.
- Both runs are kept: [`attempts/price_forecast_metrics_run1_l2_objective.json`](ml/attempts/price_forecast_metrics_run1_l2_objective.json).
- No other tuning was done on the test months.

**By crop.** The model beats "last value" for every crop. Tomato gains most: ₹{{a_tomato_model}} vs ₹{{a_tomato_last}}. Onion is ₹{{a_onion_model}} vs ₹{{a_onion_last}}, potato ₹{{a_potato_model}} vs ₹{{a_potato_last}}.

{{a_by_commodity}}

**By reporting segment.** Frequent reporters (≥ 15 report days in the prior 30) vs sparse reporters:

{{a_by_segment}}

Sparse reporters are harder for every method (MAE ₹{{a_sparse_model}} vs ₹{{a_frequent_model}} for the model). The model's advantage holds in both segments (sparse: ₹{{a_sparse_model}} vs ₹{{a_sparse_last}} for "last value").

**By test month:**

{{a_by_fold}}

**Prediction band (raw, before calibration):** p10–p90 coverage is {{a_coverage}}, against a target of about 80%. The calibration below fixes most of the gap.

### Was the median objective chosen fairly? Check on a pre-test validation window

The switch from the L2 (mean) to the L1 (median) objective was made *after* seeing the test-month results. To validate it independently, both objectives were re-run as a walk-forward on **Nov 2024 – Apr 2025**, using only targets dated **before 2025-05-01**, i.e. no test-month data at all (`python -m mandipulse ml validate-forecast`, [`forecast_validation_metrics.json`](ml/forecast_validation_metrics.json)):

{{v_table}}

By validation month (MAE, ₹/qtl):

{{v_by_fold}}

- **Winner on validation: {{v_winner}}.** L1 vs L2: {{v_l1_vs_l2}} lower MAE.
- Against the best baseline on validation: L1 is {{v_l1_vs_base}} better and L2 is {{v_l2_vs_base}} better.

{{v_verdict}}

### Prediction band calibration (p10–p90)

The raw quantile band was too narrow. It was widened with a simple conformal (CQR-style) correction fitted **only on the validation window above**:
- score per row = how far the actual price fell outside the band, in log terms;
- the three quantile models are fitted separately, so on a few rows the band edges cross the median; they are clipped to it (p10 ≤ p50 ≤ p90, the median itself unchanged);
- per crop, the band is widened by the score quantile that gives 80% coverage on validation (log widening: {{cal_qhat}}).

Validation coverage went from {{cal_val_before}}% to {{cal_val_after}}%. On the untouched test months it went from **{{cal_test_before}}% to {{cal_test_after}}%**; the median band width went from {{cal_width_before}}% to {{cal_width_after}}% of the forecast.

{{cal_table}}

Caveats: the gain is small, and calibration is not uniform. Potato already had about 80% coverage on validation, so its band was slightly *narrowed*, and its test coverage fell. I did not change the method after seeing this, because that would be tuning on the test months again. Shocks (the 2023 tomato spike) stay far below 80% whatever the calibration.

The served forecasts (`ml.price_forecast`, `ml.price_forecast_backtest`, the app) use the calibrated band.

### Stress test: July–August 2023 tomato spike

The model was trained only on targets before 2023-07-01 and evaluated on July–August 2023. Overall it beats the best baseline by {{a_stress_improvement}} on MAE:

{{a_stress_overall}}

Tomato only (the spike):

{{a_stress_tomato}}

**What happened** (`reports/figures/ml_stress_test_tomato_jul2023.png`, three Uttar Pradesh markets):
- **The rise:** every method lagged the sudden rise in early July (prices went from about ₹1,000 to ₹7,000+ in two weeks). A 7-day-ahead model cannot see a shock that has not started.
- **The plateau:** the model sat about 10% *below* the high plateau. It "expects" reversion.
- **The fall:** it turned down several days earlier than "last value" in the mid-August collapse.
- **Overall:** the error is large for everyone (tomato MAE ₹{{a_stress_tomato_model}} vs ₹{{a_stress_tomato_last}} for "last value"), and band coverage fell to {{a_stress_coverage}}.

**Honest takeaway:** a useful but modest improvement in normal times; no magic in a shock.

---

## Model B: crash early warning

### Headline: on days when the price has *not yet* started falling, the model ranks crash risk about twice as well as the seasonal rule, and more than three times as well outside December. About 3 in 10 of its early warnings come true, around a week ahead.

**Why this is the headline.** {{b_share_falling}}% of labelled crashes occur when the price is *already* below 90% of its trailing 30-day median on the day of the label. The fall has already begun, so flagging those days is easy and inflates any "all days" metric. The useful question for a farmer is whether the model can warn **before** the fall. So the headline is measured only on days when the price was still ≥ 90% of its median:

{{b_not_falling}}

**Same, excluding December** (where crashes are seasonal and easy to anticipate):

{{b_not_falling_other}}

- PR-AUC **{{b_nf_lightgbm_pr_auc}}** vs **{{b_nf_seasonal_rule_pr_auc}}** for the seasonal rule. Outside December: **{{b_nfo_lightgbm_pr_auc}}** vs **{{b_nfo_seasonal_rule_pr_auc}}**, which is {{b_nfo_lightgbm_lift_over_prevalence}}× the base rate of {{b_nfo_prev}}%.
- At the validated alert threshold: precision **{{b_nf_lightgbm_precision_pct}}%**, recall {{b_nf_lightgbm_recall_pct}}%. The precision ≥ 0.6 target is **not** met for genuine early warnings.
- Correct early warnings arrive on average **{{b_nf_lightgbm_avg_lead_days_true_alerts}} days** before the first low report.

**Setup**
- **Label (decision 2026-10-04):** a crash at day *t* means that on ≥ 2 report days in the next 14, the price is below 70% of its trailing 30-day median. Labels exist only for real report days.
- **Features:** Model A's features plus 7/14-day slopes, the previous day's state share of falling markets, and the historical crash rate for the crop × month (training data only).
- **Validation (deviation from the May–Oct 2025 window, which has no December):** yearly expanding folds, with test years 2022, 2023, 2024 and Jan–Oct 2025. For each test year the alert threshold is chosen on the *previous* year, by a model that never saw that year, targeting precision ≥ 0.6.

{{b_thresholds}}

### All days (flattering: most of these "crashes" are already under way)

{{b_all}}

**December:**

{{b_december}}

**Other months:**

{{b_other}}

The all-days precision of {{b_all_lightgbm_precision_pct}}% and recall of {{b_all_lightgbm_recall_pct}}% look strong. Most of that comes from recognising falls that have already started (those days have a crash rate above 40%), not from foresight.

### Verdict

{{b_verdict}}

- The model beats the seasonal rule in every segment, including on not-yet-falling days outside December.
- In December the seasonal rule alone is strong (PR-AUC {{b_dec_seasonal_rule_pr_auc}}). The model adds which markets will crash (PR-AUC {{b_dec_lightgbm_pr_auc}}).
- **Logistic regression is almost as good as LightGBM** (PR-AUC {{b_nfo_logistic_pr_auc}} vs {{b_nfo_lightgbm_pr_auc}} on the hardest segment). The signal is mostly simple momentum. LightGBM is served; the logistic weights are shown in the app for transparency.

## Model C: market segments

- **Features (per market × crop series with ≥ 180 report days):** price CV, average price index vs the same-day state median, reporting frequency, seasonal amplitude, crash rate, and the number of other town locations within 50 km.
- **Method:** standardised features (log of the town count), KMeans.
- **Data:** clustered on the sensitivity data, so the suspect-low series are included and can be located.
- **Silhouette:** {{c_silhouette}}. The scores for k = 3–5 are within 0.02 of each other, so the **most detailed k within 0.02 of the best** was chosen: **k = {{c_k}}**. Its segments are distinct and nameable; k = 3 merged under-priced and premium markets.

**Cluster profiles** (medians; names come from the centroid z-scores):

{{c_profiles}}

**Where the suspect-low series landed:** of the {{c_n_suspect}} suspect-low series with enough history, the split is {{c_suspect}}. Most fall in the small "Erratic & under-priced, thin reporting" segment: very volatile, very seasonal, rarely reporting and below the state price. That fits the suspicion that their low prices are data problems rather than a real market type. They remain flagged for the CEDA cross-check.

---

## Explainability (SHAP)

- **Method:** exact TreeSHAP (LightGBM `pred_contrib`) on 50,000 sampled rows per model.
- **Plots:** `reports/figures/shap_price_forecast.png` and `shap_crash_risk.png`.
- **Direction column:** the rank correlation between a feature's value and its SHAP value (+ means higher values push the prediction up).

### Model A: top drivers

{{shap_price_forecast}}

**Top 5 drivers in plain English:**
1. **Regional momentum** (`state_change_7_prev1`, +): if the state-wide median price rose over the past week (as of yesterday), this market's price is forecast to rise too. Markets move with their region.
2. **Distance from the regional price** (`state_rel_prev1`, −): a market priced above yesterday's state median tends to fall back towards it, and one priced below tends to catch up. Prices converge across nearby markets.
3. **Current price level** (`lp_t`, −): unusually high prices tend to come down and low ones go up (mean reversion).
4. **Which market** (`market_key`): some markets systematically behave differently, e.g. how fast they follow regional moves.
5. **Time of year** (`week_of_year`, +, weaker): the calendar shifts the expected change, e.g. the weeks before a crop's seasonal peak.

### Model B: top drivers

{{shap_crash_risk}}

**Top 5 drivers in plain English:**
1. **Seasonal crash history** (`hist_crash_rate`, +): crop × months that crashed often in the training years (above all December) carry much higher risk.
2. **Which market** (`market_key`): some markets crash far more often than others.
3. **Price below its recent average** (`roll_mean_30_rel`, +): when the 30-day average is well above today's price, the fall has already started and a sustained drop is likely.
4. **Negative momentum** (`momentum_30`, −): the same signal from the other side. The further today's price sits below its 30-day mean, the higher the risk.
5. **Neighbours already falling** (`state_share_falling_prev1`, +): when a large share of the state's markets were already falling yesterday, a local crash becomes much more likely.

---

## How to quote these results

Honest one-sentence claims (each backed by a table above):

1. "I built a 7-day mandi price forecast (LightGBM, walk-forward validated) that cut average error by **{{a_improvement}}** versus the best simple baseline, 'next week = today', and I checked the model choice on a separate pre-test window."
2. "For crash early warning, on days *before* prices start falling, my model ranked risk about **2× better than a seasonal rule** (PR-AUC {{b_nf_lightgbm_pr_auc}} vs {{b_nf_seasonal_rule_pr_auc}}; {{b_nfo_lightgbm_pr_auc}} vs {{b_nfo_seasonal_rule_pr_auc}} outside December). About **3 in 10 warnings came true**, around **{{b_nf_lightgbm_avg_lead_days_true_alerts}} days ahead**."
3. "I found that {{b_share_falling}}% of labelled 'crashes' were already under way when labelled, so I report the early-warning subset as the headline instead of the flattering all-days score."
4. "I calibrated the forecast's p10–p90 range with a conformal correction fitted on a validation window, raising test coverage from {{cal_test_before}}% to {{cal_test_after}}% (target 80%)."

## Limitations

- **The forecast gain is modest.** {{a_improvement}} lower MAE than "last value" is below the 10% target. Day-to-day mandi prices are close to a random walk at a 7-day horizon, and a large share of error comes from sudden shocks (the 2023 tomato spike) that no price-history model can foresee. Weather, arrivals (from CEDA) and policy events would be the next features to try.
- **The raw prediction band was too narrow.** It is now calibrated on a validation window (test coverage {{cal_test_before}}% → {{cal_test_after}}%), but in shocks such as the 2023 tomato spike coverage still drops well below 80%.
- **Crash labels are common and seasonal.** Most labelled crashes are already under way at *t*. Genuine early warnings are possible, with about 6 days' lead, but at roughly 30% precision.
- **Test period:** the walk-forward window (May–Oct 2025) falls in a year when reporting was already thinning. Results for 2025-11 onward, after the source change, are not evaluated.
- **Regional mix:** most rows come from Uttar Pradesh, so metrics are dominated by UP markets.
- **Clusters are descriptive.** Silhouette scores are low (about 0.2), so the segments overlap; they are useful labels, not hard categories.
