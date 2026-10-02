# Data Sources

Last updated: 2026-10-02 (Phase 0).

Every number on this page comes from a query in [`analysis/queries/phase0/`](../analysis/queries/phase0/), and its output is saved in [`reports/tables/phase0/`](../reports/tables/phase0/). To reproduce:

```bash
python -m mandipulse profile-kaggle              # ~15 s on the Parquet files
python -m mandipulse profile-kaggle --check-csv  # also re-counts the 6.9 GB CSV copy
```

## Source order

| Priority | Source | Role | Status |
|---|---|---|---|
| 1 | Kaggle archive: *Daily Market Prices of Commodity India (2001-2026)* | **Primary history** (2001-01-10 → 2026-04-21) | In repo folder, profiled below |
| 2 | CEDA Agri Market Data (Ashoka University) | Cross-check of prices + **arrival quantities** (the Kaggle archive has none) | Token pending (`CEDA_API_TOKEN` in `.env`); not called yet |
| 3 | data.gov.in daily mandi API (Agmarknet) | **Daily incremental feed**, later | Unreachable for the user right now; not called |

All three sources ultimately come from Agmarknet, so they should agree where they overlap. The `source` column (`kaggle_archive`, `ceda`, `datagov_daily`) records where each row came from.

---

## 1. Kaggle archive (primary, historical)

| Item | Value |
|---|---|
| Title | Daily Market Prices of Commodity India (2001-2026) |
| Author | khandelwalmanas (Kaggle) |
| Licence | GODL-India (Government Open Data License – India): reuse allowed with attribution |
| Upstream | Agmarknet (via data.gov.in) |
| Local location | Parquet: `data/raw/kaggle/` (used). CSV copy: `csv/` (not used; **safe to delete**). Both **gitignored** |
| Layout | One file per calendar year, `2001` … `2026`, identical content in CSV and Parquet |

### 1.1 Files and size

| format | files | total_gb |
|---|---|---|
| csv | 26 | 6.93 |
| parquet | 26 | 0.67 |

CSV and Parquet hold exactly the same rows: both have **75984017 rows**, first date 2001-01-10, last date 2026-04-21 (`99_csv_parquet_parity`). **We use Parquet only.** It is 10× smaller, typed, and DuckDB reads it in place. The CSV copy in `csv/` is redundant and can be deleted.

<details><summary>Per-file sizes (MB)</summary>

| year | csv_mb | parquet_mb |
|---|---|---|
| 2001 | 0.9 | 0.1 |
| 2002 | 25.6 | 2.1 |
| 2003 | 70.2 | 5.9 |
| 2004 | 67.1 | 6 |
| 2005 | 90.1 | 9 |
| 2006 | 170 | 15.9 |
| 2007 | 203.6 | 18.4 |
| 2008 | 220 | 20 |
| 2009 | 210.8 | 20.1 |
| 2010 | 229 | 21.8 |
| 2011 | 245.6 | 23.5 |
| 2012 | 267.3 | 26 |
| 2013 | 277.7 | 26.6 |
| 2014 | 278.2 | 26.8 |
| 2015 | 313.6 | 30.9 |
| 2016 | 311.9 | 30.5 |
| 2017 | 353 | 34.5 |
| 2018 | 370.7 | 36.2 |
| 2019 | 375 | 36.5 |
| 2020 | 308.2 | 29.6 |
| 2021 | 332.6 | 31.7 |
| 2022 | 390.2 | 37.6 |
| 2023 | 384.5 | 37.1 |
| 2024 | 507.7 | 44.4 |
| 2025 | 547.1 | 62.7 |
| 2026 | 59.8 | 6.9 |

</details>

### 1.2 Columns and types

| Raw column | Raw Parquet type | Read as | Notes |
|---|---|---|---|
| `State` | string | VARCHAR | |
| `District` | string | VARCHAR | |
| `Market` | string | VARCHAR | Naming changed in Nov 2025, see 1.6 |
| `Commodity` | string | VARCHAR | |
| `Variety` | string | VARCHAR | |
| `Grade` | string | VARCHAR | e.g. FAQ, Local, Medium |
| `Arrival_Date` | string `YYYY-MM-DD` | DATE | All 75984017 values parse; none null |
| `Min_Price` | DOUBLE (**INT64 in 2001.parquet**) | DOUBLE | ₹ per quintal |
| `Max_Price` | DOUBLE | DOUBLE | ₹ per quintal |
| `Modal_Price` | DOUBLE (**INT64 in 2001.parquet**) | DOUBLE | ₹ per quintal |
| `Commodity_Code` | INT64 | BIGINT | Agmarknet code (Tomato 78, Onion 23, Potato 24) |

There is **no arrivals/quantity column**, so arrival quantities must come from CEDA. Because the types drift between files, every read must use `union_by_name=true` and cast prices to DOUBLE (done in `src/mandipulse/profiling.py`).

### 1.3 Overall coverage (`03_overall_summary`, `04_rows_by_file`)

| Metric | Value |
|---|---|
| Rows | 75984017 |
| Date range | 2001-01-10 → 2026-04-21 |
| States (raw spellings) | 34 |
| Commodities | 389 |
| Districts (state × district) | 654 |
| Markets (state × district × market, raw names) | 7018 |

**The archive ends on 2026-04-21, about 5½ months before today (2026-10-02).** Later data will have to come from CEDA or data.gov.in.

`2026.parquet` also holds **11217 rows dated 2025-12-30**. `2025.parquet` also ends on 2025-12-30, and only 10 of those rows appear in both files (`18_cross_file_overlap`). Treat the two files as one stream and dedupe on the key.

### 1.4 Exact spellings (`05_name_spellings_commodity`, `06_name_spellings_state`)

**Commodities.** The spec's names match the archive exactly:

| Commodity | Code | Rows (all states) | |
|---|---|---|---|
| `Potato` | 24 | 3248834 | in scope |
| `Onion` | 23 | 3168490 | in scope |
| `Tomato` | 78 | 2818577 | in scope |
| `Onion Green` | 358 | 162206 | **exclude**: spring onion, different product |
| `Sweet Potato` | 152 | 154856 | **exclude**: different product |

Match with **exact equality** (`commodity in (...)`), never `LIKE '%onion%'`.

**States.** `Maharashtra`, `Madhya Pradesh`, `Uttar Pradesh`, `Gujarat` (final scope) and `Karnataka`, `Tamil Nadu` (dropped) are spelled exactly like this. Other spellings to know about:
- `Uttrakhand` (2002 → 2025-11-05) became `Uttarakhand` (2025-11-29 →). This is the same Nov-2025 source change as 1.6, and needs an alias seed if Uttarakhand is ever added.
- `Chattisgarh` (not "Chhattisgarh"), `Pondicherry`, `NCT of Delhi`, `Andaman and Nicobar`.
- `Jharkhand` stops at 2023-01-24.

District names are the older ones (e.g. `Ahmednagar`, `Sholapur`, `Bangalore`), not the newer official renames.

### 1.5 Coverage of the profiled states

Profiled: Tomato / Onion / Potato × the four original spec states (Maharashtra, Karnataka, Madhya Pradesh, Tamil Nadu) **plus** the two replacements (Uttar Pradesh, Gujarat). Final scope (section 4): **Maharashtra, Madhya Pradesh, Uttar Pradesh, Gujarat**. Profiled total: **3779078 rows**, 2001 → 2026.

**Rows per commodity × state × year** (`07_scope_rows_by_year`):

| commodity | state | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 124 | 847 | 1899 | 2421 | 2651 | 2538 | 4523 | 3880 | 5908 | 6337 | 5762 | 5312 | 5241 | 5830 | 6437 | 5624 | 4909 | 5587 | 4846 | 3986 | 3953 | 5132 | 5682 | 6646 | 6037 | 627 |
| Onion | Karnataka | 14 | 3551 | 4072 | 3331 | 3130 | 2132 | 3211 | 3467 | 3809 | 3944 | 4737 | 5699 | 4024 | 3931 | 4718 | 4505 | 4046 | 4087 | 3890 | 5236 | 5002 | 5404 | 4996 | 4355 | 1970 | 393 |
| Onion | Madhya Pradesh |  | 815 | 1422 | 1164 | 501 | 3976 | 9495 | 7122 | 4054 | 2710 | 3460 | 3646 | 3841 | 4224 | 5285 | 5630 | 6252 | 7515 | 9644 | 6060 | 9267 | 13038 | 12165 | 8514 | 13219 | 1081 |
| Onion | Maharashtra | 247 | 1157 | 3452 | 4237 | 5127 | 2916 | 6912 | 3177 | 8414 | 8994 | 8426 | 7355 | 7606 | 5777 | 10481 | 12964 | 12191 | 13199 | 12885 | 12000 | 14677 | 14713 | 16266 | 16744 | 14270 | 1449 |
| Onion | Tamil Nadu |  |  |  | 1 | 41 | 59 | 115 | 101 | 191 | 310 | 250 | 100 | 13 | 16 |  | 2 | 1 | 5 |  |  |  |  | 18 | 29573 | 45528 | 6551 |
| Onion | Uttar Pradesh |  | 801 | 7454 | 6380 | 8160 | 12285 | 17071 | 21130 | 19128 | 30044 | 33508 | 24927 | 26227 | 26586 | 27541 | 23232 | 37172 | 49232 | 47269 | 50538 | 50981 | 52508 | 51633 | 51538 | 47941 | 1448 |
| Potato | Gujarat | 95 | 610 | 1496 | 2260 | 2588 | 3434 | 4136 | 4814 | 5236 | 5265 | 4565 | 4376 | 4266 | 4748 | 5046 | 4974 | 4387 | 4621 | 5038 | 3337 | 3376 | 3795 | 4602 | 6503 | 6520 | 601 |
| Potato | Karnataka | 4 | 2230 | 2718 | 2322 | 2433 | 2481 | 2146 | 2573 | 2375 | 2933 | 3473 | 4216 | 2875 | 2667 | 3252 | 2810 | 2788 | 2740 | 2593 | 4389 | 4315 | 4387 | 3939 | 3112 | 1860 | 271 |
| Potato | Madhya Pradesh |  | 675 | 1319 | 1125 | 722 | 691 | 333 | 290 | 1137 | 2253 | 3656 | 3758 | 3379 | 3983 | 5061 | 5377 | 6757 | 7124 | 9296 | 5358 | 8599 | 11269 | 10068 | 2231 | 5281 | 510 |
| Potato | Maharashtra | 247 | 1120 | 2141 | 2454 | 3419 | 3811 | 3447 | 2780 | 3783 | 3802 | 3533 | 3081 | 3054 | 2773 | 4071 | 6060 | 5415 | 5581 | 4863 | 4485 | 6274 | 6273 | 7243 | 7221 | 6205 | 694 |
| Potato | Tamil Nadu |  |  |  |  |  |  | 20 | 101 | 185 | 255 | 239 | 110 |  | 2 |  |  |  |  |  |  |  |  |  | 26304 | 34417 | 4327 |
| Potato | Uttar Pradesh |  | 901 | 8598 | 7093 | 9072 | 13574 | 18643 | 22732 | 20307 | 31466 | 36518 | 25171 | 28396 | 27097 | 28350 | 24217 | 44348 | 57623 | 58124 | 54228 | 54956 | 56978 | 56109 | 55332 | 50387 | 2294 |
| Tomato | Gujarat | 56 | 491 | 1297 | 2117 | 2661 | 2955 | 4489 | 5573 | 5690 | 6020 | 5679 | 5279 | 5046 | 5553 | 5945 | 5737 | 5064 | 6606 | 6724 | 5436 | 4775 | 4803 | 5320 | 6951 | 7032 | 687 |
| Tomato | Karnataka | 5 | 2572 | 3135 | 2391 | 2768 | 2179 | 2796 | 3222 | 3917 | 5138 | 5215 | 6516 | 4360 | 4641 | 5918 | 5105 | 5065 | 5558 | 5463 | 7786 | 7698 | 7553 | 7037 | 5410 | 3150 | 437 |
| Tomato | Madhya Pradesh |  | 595 | 1183 | 1006 | 631 | 376 | 243 | 398 | 1256 | 2360 | 3756 | 3899 | 3774 | 4444 | 5596 | 5777 | 6244 | 7334 | 9957 | 5806 | 9043 | 11935 | 10121 | 1650 | 6327 | 430 |
| Tomato | Maharashtra | 106 | 224 | 1545 | 2270 | 3009 | 3592 | 3817 | 3529 | 5355 | 6002 | 5057 | 4692 | 4998 | 5113 | 7024 | 10206 | 10538 | 10655 | 10055 | 9103 | 10682 | 10480 | 10869 | 10765 | 9508 | 923 |
| Tomato | Tamil Nadu |  |  |  |  | 110 | 209 | 228 | 219 | 199 | 226 | 228 | 71 | 8 |  |  |  |  |  |  |  |  |  | 2 | 30166 | 41417 | 5172 |
| Tomato | Uttar Pradesh |  | 585 | 5243 | 3213 | 3477 | 4053 | 6106 | 7621 | 6954 | 14745 | 15972 | 12811 | 17455 | 16614 | 19553 | 18003 | 30539 | 45709 | 50297 | 49786 | 50885 | 50916 | 49421 | 51211 | 47902 | 1588 |

**Markets reporting per commodity × state × year** (`08_scope_markets_by_year`). These use raw names, so 2025–2026 counts are inflated by the ` APMC` renaming (1.6):

| commodity | state | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 6 | 7 | 18 | 18 | 36 | 36 | 46 | 38 | 35 | 37 | 31 | 34 | 31 | 41 | 40 | 37 | 24 | 27 | 27 | 29 | 27 | 25 | 30 | 30 | 56 | 28 |
| Onion | Karnataka | 3 | 58 | 54 | 54 | 53 | 50 | 49 | 50 | 55 | 60 | 60 | 55 | 54 | 43 | 41 | 36 | 40 | 39 | 41 | 51 | 39 | 40 | 45 | 41 | 48 | 29 |
| Onion | Madhya Pradesh |  | 9 | 9 | 7 | 8 | 111 | 83 | 120 | 88 | 24 | 31 | 38 | 29 | 39 | 36 | 43 | 51 | 58 | 63 | 61 | 69 | 72 | 80 | 77 | 132 | 73 |
| Onion | Maharashtra | 4 | 14 | 29 | 49 | 62 | 66 | 82 | 72 | 88 | 84 | 81 | 75 | 80 | 77 | 84 | 90 | 82 | 87 | 88 | 89 | 86 | 87 | 106 | 106 | 166 | 89 |
| Onion | Tamil Nadu |  |  |  | 1 | 2 | 2 | 5 | 2 | 3 | 4 | 3 | 2 | 1 | 3 |  | 1 | 1 | 2 |  |  |  |  | 2 | 247 | 331 | 332 |
| Onion | Uttar Pradesh |  | 25 | 42 | 39 | 49 | 88 | 107 | 124 | 121 | 174 | 164 | 165 | 149 | 185 | 191 | 193 | 214 | 207 | 210 | 214 | 208 | 204 | 204 | 212 | 317 | 163 |
| Potato | Gujarat | 4 | 5 | 13 | 13 | 27 | 27 | 37 | 36 | 31 | 28 | 26 | 26 | 21 | 31 | 34 | 29 | 19 | 25 | 26 | 25 | 22 | 20 | 25 | 26 | 49 | 25 |
| Potato | Karnataka | 3 | 34 | 40 | 39 | 40 | 34 | 43 | 43 | 46 | 41 | 44 | 50 | 48 | 30 | 36 | 29 | 30 | 29 | 27 | 41 | 35 | 31 | 39 | 33 | 41 | 27 |
| Potato | Madhya Pradesh |  | 8 | 8 | 6 | 7 | 9 | 6 | 5 | 18 | 22 | 30 | 34 | 27 | 35 | 31 | 33 | 36 | 41 | 54 | 50 | 52 | 54 | 63 | 40 | 73 | 47 |
| Potato | Maharashtra | 4 | 11 | 17 | 24 | 31 | 41 | 43 | 35 | 44 | 39 | 36 | 38 | 39 | 36 | 40 | 47 | 37 | 36 | 34 | 41 | 39 | 39 | 41 | 41 | 77 | 38 |
| Potato | Tamil Nadu |  |  |  |  |  |  | 3 | 2 | 3 | 3 | 2 | 2 |  | 1 |  |  |  |  |  |  |  |  |  | 226 | 252 | 303 |
| Potato | Uttar Pradesh |  | 27 | 44 | 41 | 50 | 92 | 116 | 127 | 125 | 177 | 170 | 166 | 151 | 188 | 191 | 196 | 222 | 218 | 218 | 220 | 215 | 213 | 214 | 219 | 369 | 189 |
| Tomato | Gujarat | 4 | 4 | 11 | 16 | 27 | 28 | 38 | 36 | 34 | 33 | 29 | 29 | 28 | 36 | 40 | 36 | 26 | 35 | 36 | 35 | 31 | 26 | 31 | 32 | 57 | 28 |
| Tomato | Karnataka | 2 | 30 | 31 | 35 | 34 | 32 | 37 | 37 | 41 | 43 | 47 | 51 | 49 | 37 | 37 | 36 | 35 | 36 | 33 | 45 | 43 | 40 | 45 | 39 | 54 | 34 |
| Tomato | Madhya Pradesh |  | 7 | 7 | 5 | 6 | 7 | 4 | 4 | 14 | 21 | 28 | 34 | 24 | 30 | 30 | 30 | 30 | 39 | 48 | 48 | 52 | 52 | 59 | 33 | 62 | 47 |
| Tomato | Maharashtra | 1 | 4 | 19 | 25 | 28 | 38 | 41 | 33 | 44 | 43 | 41 | 40 | 45 | 43 | 48 | 56 | 51 | 50 | 50 | 59 | 55 | 56 | 55 | 56 | 90 | 46 |
| Tomato | Tamil Nadu |  |  |  |  | 4 | 3 | 5 | 3 | 4 | 2 | 2 | 1 | 1 |  |  |  |  |  |  |  |  |  | 1 | 250 | 303 | 347 |
| Tomato | Uttar Pradesh |  | 21 | 34 | 25 | 29 | 34 | 41 | 43 | 56 | 107 | 89 | 87 | 82 | 110 | 114 | 122 | 181 | 196 | 204 | 207 | 202 | 201 | 206 | 208 | 337 | 169 |

**Date gaps, state level.** These are calendar days per year on which at least one market in the state reported (`10_scope_date_gaps`):

| commodity | state | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 63 | 297 | 330 | 357 | 354 | 351 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 364 | 364 | 365 | 365 | 365 | 353 | 360 | 362 | 360 | 359 | 361 | 335 | 98 |
| Onion | Karnataka | 7 | 346 | 358 | 358 | 336 | 353 | 340 | 344 | 350 | 337 | 351 | 366 | 324 | 344 | 360 | 355 | 354 | 352 | 348 | 354 | 362 | 363 | 354 | 351 | 310 | 87 |
| Onion | Madhya Pradesh |  | 254 | 358 | 352 | 304 | 214 | 275 | 300 | 309 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 356 | 365 | 365 | 365 | 362 | 339 | 100 |
| Onion | Maharashtra | 171 | 322 | 358 | 362 | 364 | 363 | 365 | 361 | 363 | 365 | 365 | 365 | 365 | 364 | 365 | 364 | 360 | 365 | 362 | 345 | 361 | 365 | 363 | 361 | 335 | 99 |
| Onion | Tamil Nadu |  |  |  | 1 | 41 | 59 | 107 | 101 | 185 | 228 | 235 | 100 | 13 | 15 |  | 2 | 1 | 5 |  |  |  |  | 18 | 207 | 319 | 101 |
| Onion | Uttar Pradesh |  | 152 | 365 | 365 | 365 | 364 | 364 | 365 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 339 | 102 |
| Potato | Gujarat | 61 | 284 | 331 | 357 | 352 | 363 | 364 | 366 | 364 | 365 | 365 | 366 | 365 | 365 | 364 | 366 | 365 | 365 | 365 | 364 | 362 | 360 | 359 | 362 | 339 | 100 |
| Potato | Karnataka | 4 | 342 | 358 | 352 | 338 | 359 | 340 | 346 | 350 | 331 | 348 | 366 | 319 | 352 | 360 | 349 | 352 | 353 | 343 | 360 | 360 | 364 | 352 | 353 | 313 | 83 |
| Potato | Madhya Pradesh |  | 251 | 359 | 354 | 333 | 311 | 237 | 223 | 277 | 365 | 365 | 366 | 365 | 365 | 364 | 366 | 365 | 365 | 365 | 357 | 365 | 365 | 364 | 354 | 335 | 94 |
| Potato | Maharashtra | 167 | 331 | 360 | 361 | 364 | 363 | 364 | 364 | 363 | 365 | 365 | 364 | 364 | 365 | 364 | 366 | 364 | 365 | 365 | 353 | 363 | 365 | 363 | 360 | 337 | 99 |
| Potato | Tamil Nadu |  |  |  |  |  |  | 17 | 101 | 185 | 227 | 235 | 110 |  | 1 |  |  |  |  |  |  |  |  |  | 195 | 319 | 101 |
| Potato | Uttar Pradesh |  | 152 | 365 | 365 | 365 | 364 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 342 | 101 |
| Tomato | Gujarat | 31 | 291 | 335 | 361 | 361 | 355 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 364 | 362 | 362 | 366 | 338 | 102 |
| Tomato | Karnataka | 5 | 342 | 357 | 354 | 334 | 344 | 343 | 346 | 348 | 353 | 360 | 366 | 354 | 363 | 364 | 363 | 364 | 364 | 358 | 366 | 365 | 365 | 364 | 357 | 326 | 94 |
| Tomato | Madhya Pradesh |  | 168 | 359 | 350 | 314 | 236 | 209 | 290 | 316 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 357 | 365 | 365 | 360 | 235 | 327 | 87 |
| Tomato | Maharashtra | 106 | 182 | 357 | 361 | 362 | 362 | 365 | 364 | 363 | 365 | 365 | 365 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 361 | 365 | 365 | 363 | 361 | 333 | 99 |
| Tomato | Tamil Nadu |  |  |  |  | 84 | 181 | 174 | 171 | 185 | 226 | 224 | 71 | 8 |  |  |  |  |  |  |  |  |  | 2 | 199 | 320 | 102 |
| Tomato | Uttar Pradesh |  | 133 | 365 | 365 | 361 | 364 | 365 | 365 | 365 | 365 | 365 | 366 | 365 | 364 | 365 | 366 | 365 | 365 | 365 | 366 | 365 | 365 | 365 | 366 | 341 | 102 |

Longest run of consecutive days with no report anywhere in the state:

| commodity | state | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 36 | 4 | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 4 | 2 | 1 | 4 | 3 | 2 | 22 | 5 |
| Onion | Karnataka | 308 | 3 | 7 | 3 | 7 | 15 | 9 | 8 | 17 | 2 | 1 | 0 | 3 | 3 | 1 | 3 | 2 | 2 | 4 | 1 | 1 | 1 | 2 | 3 | 27 | 5 |
| Onion | Madhya Pradesh |  | 14 | 1 | 7 | 3 | 8 | 4 | 5 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 3 | 26 | 4 |
| Onion | Maharashtra | 32 | 4 | 1 | 1 | 1 | 1 | 0 | 3 | 2 | 0 | 0 | 1 | 0 | 1 | 0 | 2 | 3 | 0 | 3 | 10 | 2 | 0 | 1 | 2 | 28 | 5 |
| Onion | Tamil Nadu |  |  |  |  | 491 | 118 | 87 | 146 | 37 | 9 | 18 | 40 | 126 | 364 |  | 834 | 168 | 377 |  |  |  |  | 1723 | 88 | 28 | 4 |
| Onion | Uttar Pradesh |  | 13 | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 4 |
| Potato | Gujarat | 36 | 5 | 2 | 2 | 2 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 4 | 3 | 2 | 24 | 3 |
| Potato | Karnataka | 308 | 10 | 7 | 3 | 7 | 13 | 9 | 2 | 17 | 2 | 1 | 0 | 4 | 3 | 1 | 4 | 3 | 2 | 6 | 1 | 1 | 1 | 1 | 3 | 24 | 5 |
| Potato | Madhya Pradesh |  | 6 | 1 | 8 | 2 | 5 | 5 | 35 | 48 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 1 | 3 | 27 | 4 |
| Potato | Maharashtra | 49 | 4 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 4 | 2 | 0 | 1 | 2 | 24 | 4 |
| Potato | Tamil Nadu |  |  |  |  |  |  | 147 | 146 | 37 | 9 | 18 | 33 |  | 701 |  |  |  |  |  |  |  |  |  | 3638 | 28 | 3 |
| Potato | Uttar Pradesh |  | 13 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 3 |
| Tomato | Gujarat | 4 | 6 | 2 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 1 | 0 | 26 | 3 |
| Tomato | Karnataka | 27 | 3 | 7 | 4 | 17 | 2 | 9 | 3 | 18 | 2 | 2 | 0 | 2 | 1 | 1 | 3 | 1 | 1 | 5 | 0 | 0 | 0 | 1 | 3 | 28 | 4 |
| Tomato | Madhya Pradesh |  | 110 | 1 | 8 | 8 | 24 | 14 | 6 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 2 | 9 | 28 | 4 |
| Tomato | Maharashtra | 125 | 50 | 2 | 2 | 1 | 2 | 0 | 1 | 2 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 1 | 2 | 28 | 4 |
| Tomato | Tamil Nadu |  |  |  |  | 5 | 40 | 73 | 12 | 34 | 9 | 18 | 19 | 265 |  |  |  |  |  |  |  |  |  | 3909 | 89 | 28 | 3 |
| Tomato | Uttar Pradesh |  | 13 | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 | 3 |

Reading these: from 2010 to 2024 every state except Tamil Nadu has a report on nearly every day at state level (Uttar Pradesh: ≥ 364 days every year). The 22–28-day gap in 2025 in **every** state is the Nov-2025 outage (1.6). Tamil Nadu has effectively **no data from 2013 to mid-2024** (gaps of 1723–3909 days).

**Date gaps, market level** (`11_scope_series_coverage`). State-level coverage hides how thin individual markets are. In the two dense years before the source change (2023-11-01 → 2025-10-31; a series = market × commodity):

| Commodity | State | Series | ≥ 180 report days | ≥ 365 report days | Median report days |
|---|---|---|---|---|---|
| Onion | Gujarat | 33 | 23 | 21 | 437 |
| Onion | Karnataka | 46 | 13 | 4 | 48 |
| Onion | Madhya Pradesh | 133 | 40 | 16 | 52 |
| Onion | Maharashtra | 109 | 70 | 42 | 259 |
| Onion | Tamil Nadu | 251 | 166 | 158 | 432 |
| Onion | Uttar Pradesh | 218 | 184 | 159 | 541.5 |
| Potato | Gujarat | 27 | 23 | 22 | 516 |
| Potato | Karnataka | 36 | 12 | 4 | 45 |
| Potato | Madhya Pradesh | 102 | 17 | 4 | 34 |
| Potato | Maharashtra | 44 | 30 | 21 | 346.5 |
| Potato | Tamil Nadu | 228 | 147 | 111 | 364 |
| Potato | Uttar Pradesh | 222 | 201 | 169 | 554 |
| Tomato | Gujarat | 35 | 28 | 24 | 504 |
| Tomato | Karnataka | 43 | 21 | 13 | 152 |
| Tomato | Madhya Pradesh | 94 | 23 | 0 | 41.5 |
| Tomato | Maharashtra | 57 | 42 | 31 | 445 |
| Tomato | Tamil Nadu | 254 | 167 | 137 | 368 |
| Tomato | Uttar Pradesh | 218 | 183 | 157 | 547.5 |

The ML spec drops series with fewer than 180 valid days. On that rule **Karnataka keeps only 12–21 series per crop and Madhya Pradesh 17–40**, even though their state-level coverage looks complete. **Uttar Pradesh keeps 183–201** and Gujarat 23–28.

**Monthly rows per state** (`09_scope_monthly_rows`, all three crops):

| month | Gujarat | Karnataka | Madhya Pradesh | Maharashtra | Tamil Nadu | Uttar Pradesh |
|---|---|---|---|---|---|---|
| 2023-10 | 1499 | 1217 | 2868 | 2829 | 7 | 13329 |
| 2023-11 | 1178 | 1186 | 2297 | 2471 | 2 | 12483 |
| 2023-12 | 1585 | 1221 | 2086 | 2913 | 2 | 13230 |
| 2024-01 | 1565 | 1012 | 604 | 2813 | 3 | 12942 |
| 2024-02 | 1633 | 1210 | 579 | 2765 | 8 | 12808 |
| 2024-03 | 1432 | 1213 | 602 | 3104 | 3 | 13010 |
| 2024-04 | 1457 | 975 | 712 | 1924 |  | 12934 |
| 2024-05 | 1797 | 1221 | 858 | 2981 | 2 | 14189 |
| 2024-06 | 1689 | 1128 | 974 | 2819 | 3300 | 13458 |
| 2024-07 | 1909 | 1197 | 998 | 3098 | 11642 | 14060 |
| 2024-08 | 1703 | 1117 | 829 | 3024 | 14720 | 13637 |
| 2024-09 | 1648 | 1043 | 963 | 2990 | 14213 | 13209 |
| 2024-10 | 1764 | 1023 | 1694 | 3069 | 14580 | 12799 |
| 2024-11 | 1595 | 766 | 1733 | 2849 | 13469 | 11992 |
| 2024-12 | 1908 | 972 | 1849 | 3294 | 14103 | 13043 |
| 2025-01 | 1952 | 1104 | 2086 | 3283 | 14404 | 13749 |
| 2025-02 | 1919 | 924 | 1822 | 2560 | 13174 | 14870 |
| 2025-03 | 2019 | 432 | 1743 | 3230 | 14145 | 15035 |
| 2025-04 | 1999 | 552 | 2382 | 3060 | 14261 | 15092 |
| 2025-05 | 2099 | 625 | 2647 | 3132 | 14260 | 16015 |
| 2025-06 | 1915 | 673 | 2539 | 3241 | 13328 | 15100 |
| 2025-07 | 2089 | 707 | 2765 | 3248 | 11532 | 15563 |
| 2025-08 | 1841 | 548 | 2730 | 2890 | 8448 | 14765 |
| 2025-09 | 1737 | 696 | 3234 | 2628 | 7912 | 13100 |
| 2025-10 | 1269 | 408 | 2169 | 1769 | 5758 | 9533 |
| 2025-11 | 151 | 23 | 174 | 152 | 488 | 878 |
| 2025-12 | 599 | 288 | 536 | 790 | 3652 | 2530 |
| 2026-01 | 683 | 336 | 448 | 926 | 4312 | 2104 |
| 2026-02 | 501 | 278 | 664 | 818 | 3801 | 999 |
| 2026-03 | 383 | 246 | 497 | 685 | 4222 | 658 |
| 2026-04 | 348 | 241 | 412 | 637 | 3715 | 1569 |

> **⚠ Flag: Madhya Pradesh gap, Jan–Sep 2024.** MP has about 600–1000 rows/month in Jan–Sep 2024 against about 2000–3000 normally, and 0 tomato series reach 180 report days in 2024 (`20_state_candidates`). MP stays in scope (it links Maharashtra, Gujarat and Uttar Pradesh geographically), but its 2024 series will be short and gappy. The ML layer's ≥ 180-day rule and gap handling must absorb this, and MP figures for 2024 need a caveat.

Karnataka (dropped) also thins from Mar 2025.

### 1.6 Source change in November 2025 (most important caveat)

Around **2025-11-04 → 2025-11-29**, the upstream data changed format (consistent with Agmarknet's portal migration):

1. **Markets were renamed with an ` APMC` suffix**: `Lasalgaon` → `Lasalgaon APMC`, `Pune` → `Pune APMC`, and so on (`15_naming_regime_change`):

| state | n_renamed_markets | latest_old_name_seen | earliest_new_name_seen |
|---|---|---|---|
| Gujarat | 40 | 2025-11-06 | 2025-11-29 |
| Karnataka | 43 | 2025-11-04 | 2025-11-29 |
| Madhya Pradesh | 85 | 2025-11-05 | 2025-12-02 |
| Maharashtra | 98 | 2025-11-04 | 2025-11-29 |
| Tamil Nadu | 177 | 2026-04-20 | 2025-12-03 |
| Uttar Pradesh | 201 | 2025-11-06 | 2025-11-29 |

   (Tamil Nadu's count is misleading. Its Uzhavar Sandhai market names already contained "APMC" before the change, and both name forms are still in use.)
   The spec's staging rule (strip "APMC" into `market_clean`) handles this, and **it is mandatory, not optional**. Without it every market splits into two series in Nov 2025.
2. **Reporting density collapsed.** The median report days per month for a market × commodity series (`16_reporting_density`) went from about 25–28 to single digits:

| month | n_series_reporting | median_report_days | median_rows |
|---|---|---|---|
| 2025-01 | 1493 | 27 | 28 |
| 2025-02 | 1490 | 25 | 27 |
| 2025-03 | 1469 | 26 | 28 |
| 2025-04 | 1487 | 26 | 28 |
| 2025-05 | 1506 | 27 | 29 |
| 2025-06 | 1522 | 26 | 27 |
| 2025-07 | 1502 | 25 | 25 |
| 2025-08 | 1446 | 24 | 24 |
| 2025-09 | 1487 | 21 | 21 |
| 2025-10 | 1456 | 15 | 15 |
| 2025-11 | 1024 | 2 | 2 |
| 2025-12 | 1098 | 7 | 7 |
| 2026-01 | 1161 | 7 | 7 |
| 2026-02 | 1201 | 5 | 5 |
| 2026-03 | 1142 | 6 | 6 |
| 2026-04 | 1767 | 4 | 4 |

   Note that density had already been **thinning since Jul 2025** (24 → 14 days/month). Nov 2025 is close to empty: 152 rows in Maharashtra against about 3000 a month normally.
   (From Jul 2024 the medians are lifted by Tamil Nadu's near-daily Uzhavar Sandhai markets.)

**Consequence:** 2025-11 → 2026-04 is a different regime. It is fine for "latest price" display, but it should not be used for ML evaluation until CEDA confirms whether the gaps are real or an artefact of the archive.

### 1.7 Tamil Nadu is a different kind of market

(`21_tamil_nadu_market_types`, Jul 2024 → Oct 2025)

| state | commodity | market_type | n_markets | n_rows | p10_modal | median_modal | p90_modal | n_modal_below_200 |
|---|---|---|---|---|---|---|---|---|
| Maharashtra | Onion | other | 104 | 22748 | 1000 | 1800 | 4000 | 0 |
| Maharashtra | Potato | other | 43 | 9663 | 1300 | 1800 | 2800 | 2 |
| Maharashtra | Tomato | other | 57 | 14954 | 700 | 1500 | 3500 | 13 |
| Tamil Nadu | Onion | other | 87 | 5736 | 50 | 4200 | 6000 | 597 |
| Tamil Nadu | Onion | uzhavar_sandhai | 163 | 66341 | 2800 | 4000 | 6500 | 7 |
| Tamil Nadu | Potato | other | 78 | 4581 | 55 | 4000 | 6000 | 538 |
| Tamil Nadu | Potato | uzhavar_sandhai | 150 | 54179 | 3200 | 4500 | 6000 | 7 |
| Tamil Nadu | Tomato | other | 88 | 5669 | 50 | 2500 | 5400 | 616 |
| Tamil Nadu | Tomato | uzhavar_sandhai | 165 | 63443 | 1500 | 2500 | 5000 | 7 |

- **Uzhavar Sandhai** markets supply about 92% of Tamil Nadu's in-scope rows in this window (e.g. 66341 of 72077 onion rows) and outnumber the other markets about 2:1. They are farmer-to-consumer markets with near-retail prices. Their medians are about 2× Maharashtra wholesale for onion and potato (₹4000–4500 vs ₹1800/qtl). That breaks the spec's assumption that modal price is a *wholesale* indicator, and comparing them with APMC prices would create fake "opportunities".
- The non-Uzhavar TN markets have a 10th percentile of **₹50/qtl**, because many rows are entered **per kg** (e.g. Ariyalur Market, 2024-06-18, onion modal = 35). About 10–12% of those rows have modal < ₹200 (`n_modal_below_200`).

### 1.8 Data-quality issues

**Whole archive** (`12_quality_overall`, `22_quality_by_year`):

| Issue | Rows | % of 75984017 |
|---|---|---|
| Null names / variety / grade | 0 | 0% |
| Null min/max/modal price | 61 | <0.001% |
| Modal ≤ 0 | 0 | 0% |
| Min ≤ 0 | 1833978 | 2.4% |
| Max ≤ 0 | 1768209 | 2.3% |
| Min > Max | 37686 | 0.05% |
| Modal outside [Min, Max] | 1786196 | 2.4% |

Most of the zero min/max rows (and therefore most "modal outside range" rows) are **2002–2017 placeholders** where only the modal price was filled in. From 2018 they fall to 5–22 thousand rows a year (about 0.1–0.5%). Min > Max persists at roughly 900–5100 rows a year through 2025.

**In scope** (`13_quality_scope`):

| Commodity | State | Rows | Min/Max ≤ 0 | Min > Max | Modal outside range | Modal < ₹50 | Modal > ₹20000 |
|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 112739 | 21 | 6 | 13 | 1 | 0 |
| Onion | Karnataka | 97654 | 31 | 6 | 16 | 20 | 0 |
| Onion | Madhya Pradesh | 144100 | 32 | 15 | 692 | 14 | 4 |
| Onion | Maharashtra | 225636 | 10 | 0 | 0 | 57 | 7 |
| Onion | Tamil Nadu | 82875 | 6 | 5 | 5 | 1349 | 3 |
| Onion | Uttar Pradesh | 724734 | 120742 | 1462 | 118630 | 11 | 0 |
| Potato | Gujarat | 100689 | 16 | 8 | 16 | 7 | 0 |
| Potato | Karnataka | 71902 | 37 | 6 | 21 | 18 | 1 |
| Potato | Madhya Pradesh | 100252 | 19 | 12 | 152 | 3 | 0 |
| Potato | Maharashtra | 103830 | 18 | 0 | 0 | 66 | 0 |
| Potato | Tamil Nadu | 65960 | 47 | 1 | 1 | 917 | 2 |
| Potato | Uttar Pradesh | 792514 | 125478 | 1439 | 123136 | 15 | 0 |
| Tomato | Gujarat | 117986 | 35 | 5 | 10 | 209 | 0 |
| Tomato | Karnataka | 115035 | 78 | 4 | 25 | 11 | 3 |
| Tomato | Madhya Pradesh | 104141 | 14 | 9 | 9 | 1 | 1 |
| Tomato | Maharashtra | 160117 | 4 | 0 | 0 | 241 | 2 |
| Tomato | Tamil Nadu | 78255 | 2 | 3 | 3 | 663 | 4 |
| Tomato | Uttar Pradesh | 580659 | 67473 | 1576 | 66360 | 3 | 0 |

- No null prices and no zero modal prices in scope.
- **Tamil Nadu** has most of the `< ₹50` rows (₹/kg entries, see 1.7). **Maharashtra** also has 241 tomato rows under ₹50; inspect them in Phase 2.
- **Madhya Pradesh onion** has 692 rows with modal outside [min, max], far more than any other non-UP pair.
- **Uttar Pradesh** shows 12–17% of rows with min/max ≤ 0 over the full history, but these are old placeholders: 34–55% of UP rows a year in 2008–2016, then **1.83% in 2018, below 0.6% from 2020, and 0.01% in 2025** (`23_scope_quality_by_year`). This is another reason to start in 2018. UP also has 520–870 min > max rows a year in 2020–2023; the staging flags handle those.
- **Gujarat tomato** has 209 rows with modal < ₹50; inspect them in Phase 2.

**Duplicates** (`14_duplicates`, profiled states): **167 exact duplicate rows**. All 167 are also the only duplicates on the spec's dedupe key `(date, state, district, market, commodity, variety, grade)`, and **none conflict** (copies always have the same modal price). The spec's dedupe rule is therefore safe.

**Variety / grade** (`17_variety_grade`): the largest variety bucket for each crop is `Other`, followed by generic labels (`Onion`, `Tomato`, `Potato`, `Local`, `Deshi`, `Bellary`, `(Red Nanital)`). Grade is mostly `FAQ` (3450111 rows) or `Local` (260083). In the dense months a market × commodity × day usually has a **single row**: the median rows per series-month equals the median report days (`16_reporting_density`). So the variety-aggregation rule (spec 7.4) changes little in practice.

---

## 2. CEDA Agri Market Data (secondary)

- Publisher: Centre for Economic Data and Analysis (CEDA), Ashoka University. Also derived from Agmarknet, cleaned and harmonised.
- Role: (a) **cross-check** Kaggle prices on overlapping dates; (b) supply **arrival quantities** (tonnes), which the Kaggle archive lacks; (c) possibly fill **2025-11 → present**, if its coverage of that period is better.
- Access: API token stored as `CEDA_API_TOKEN` in `.env` (user will add). **Not called yet.** Endpoints, field names, rate limits, and licence terms are to be verified in Phase 1 before any code depends on them.

## 3. data.gov.in daily API (tertiary, later)

- Resource ID in the spec: `9ef84268-d588-465a-a308-a864a43d0070`. **Unverified**, because data.gov.in is currently unreachable for the user.
- It becomes the daily incremental feed once reachable. The client must write the same raw schema with `source = 'datagov_daily'`.

## 4. Scope decision (2026-10-02)

Recommended in Phase 0 and **confirmed by the user**. Applied in `config/settings.yaml`.

| Dimension | Original spec | Decided | Why |
|---|---|---|---|
| Crops | Tomato, Onion, Potato | **Tomato, Onion, Potato.** `Onion Green` and `Sweet Potato` explicitly excluded | 2.8–3.2 M rows each nationally; spellings match exactly. The look-alikes are different products. |
| States | MH, KA, MP, TN | **Maharashtra, Madhya Pradesh, Uttar Pradesh, Gujarat** | **Tamil Nadu dropped**: about 92% of its rows since 2024 come from Uzhavar Sandhai farmer-to-consumer markets with retail-like prices (about 2× Maharashtra wholesale); its other markets often enter prices **per kg**; and it has no history from 2013 to mid-2024 (1.7). **Karnataka dropped**: thin at market level, with only 2–24 series per crop reaching ≥ 180 report days a year, falling to 2–6 in 2025 (`20_state_candidates`). **Uttar Pradesh added**: 143–185 such series per crop in every year 2018–2025, the most of any state. **Gujarat added**: 9–25, rising. MH, MP, GJ and UP form one contiguous block, which matters for the ≤ 100 km pair analysis. |
| Years | backfill_start 2023-01-01 | Load from **2018-01-01**. Rows tagged `period = 'main'` (2018-01-01 → 2025-10-31) or `period = 'post_format_change'` (2025-11-01 →) | From 2018 the zero-price placeholders drop below 2% (UP) and 0.5% (overall). Eight seasonal cycles give the crash model enough rare events. The main window ends before the Nov-2025 source change (1.6). |
| ML test window | last 6 months | **May → Oct 2025** walk-forward test months | Last 6 months of the main period. |

Known caveat carried forward: the **Madhya Pradesh Jan–Sep 2024 gap** (1.5).
