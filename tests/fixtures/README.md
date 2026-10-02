# Test fixtures — SYNTHETIC, TEST-ONLY

Everything in this folder is **synthetic** and exists only for tests and CI.
It must never be used for analysis or reported numbers (spec §0.4).

| File | What it is |
|---|---|
| `synthetic_raw_sample.csv` | Made-up prices on real market names (so reference seeds resolve), in the Kaggle archive's column layout. CI loads it with `python -m mandipulse load --source-glob tests/fixtures/synthetic_raw_sample.csv` and runs `dbt build` on it. |
| `make_synthetic_raw_sample.py` | Deterministic generator for the CSV above (fixed seed); lists the deliberate edge cases. |
