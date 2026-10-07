# Screenshots for the README

**Status (2026-10-07):** the app screenshots are done, taken from the live app at https://mandi-pulse.streamlit.app/. The Power BI screenshots are still to come; when they are added, put them back into the README's "Screenshots" section. Save each screenshot under the **file name** listed below. PNG works best: about 1600 px wide, light theme, browser zoom 100%, and no personal bookmarks or tabs visible.

## Streamlit app

Run the app with `streamlit run app/Home.py`. In the app's ⋮ menu → **Settings**, choose the **Light** theme.

| File | Page | Settings before taking it | What must be visible |
|---|---|---|---|
| `app_home.png` | Home | – | Banner "Data as of 31 Oct 2025", the 3 metrics, the pages table, and the attribution in the sidebar |
| `app_best_mandi.png` | Best Mandi | Crop **Tomato**; market **Gujarat › Ahmedabad › Ahmedabad**; 100 km; **Mid** | The 3 metrics (₹1,800 · 2 of 8 · ₹122), the ranked table and the map. Wait until the map tiles have loaded |
| `app_price_outlook.png` | Price Outlook | Crop **Tomato**; market **Uttar Pradesh › Fatehpur › Fatehpur** | Chart with the shaded band, black actuals, blue forecast and orange dashed "same as today" line; the latest-forecast box; accuracy metrics |
| `app_crash_risk.png` | Crash Risk | All crops, all states | "Falling now" table (confirmed first) and the "Early warning" box with "About 3 in 10…" plus High/Medium/Low counts. Scroll so both sections are in view, or take two shots and keep the first |
| `app_market_explorer.png` | Market Explorer | Tab "Price-trapped districts", crop **Tomato** | The trapped-district count and table |
| `app_methodology.png` | Methodology | Scroll to "How good are the models?" | The forecast table and the crash early-warning headline |
| `app_methodology_data.png` | Methodology | Top of the page | Data sources and the cleaning summary |

## Power BI

Follow [powerbi/DASHBOARD_SPEC.md](../../powerbi/DASHBOARD_SPEC.md), section 7.

| File | Page | Slicers |
|---|---|---|
| `powerbi_01_overview.png` | Overview | all crops, all years, scenario = mid |
| `powerbi_02_price_spread.png` | Price Spread | Tomato, Maharashtra |
| `powerbi_03_seasonality.png` | Seasonality & Volatility | all crops |
| `powerbi_04_price_trapped.png` | Price-Trapped Districts | Tomato |
| `powerbi_05_forecast_alerts.png` | Forecast & Alerts | Fatehpur, Tomato |

In Power BI, hide the Filters pane before capturing (View → Filters pane).
