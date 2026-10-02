"""Run dbt with .env loaded and config/settings.yaml passed as --vars.

python -m mandipulse dbt build
python -m mandipulse dbt test --select fact_daily_price
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from mandipulse.config import PROJECT_ROOT, get_settings  # importing config loads .env

DBT_DIR = PROJECT_ROOT / "dbt" / "mandipulse"


def dbt_vars() -> dict:
    cfg = get_settings()
    bounds = cfg["quality"]["unit_bounds_per_qtl"]
    low = cfg["quality"]["persistent_low"]
    geo, opp, access = cfg["geo"], cfg["opportunity"], cfg["district_access"]
    crash = cfg["ml"]["crash"]
    return {
        "commodities": cfg["scope"]["commodities"],
        "periods": list(cfg["periods"]),
        "main_end": cfg["periods"]["main"]["end"],
        "unit_min_per_qtl": bounds["min"],
        "unit_max_per_qtl": bounds["max"],
        "outlier_log_ratio": cfg["quality"]["outlier_log_ratio"],
        "outlier_window_days": cfg["quality"].get("outlier_window_days", 30),
        "outlier_min_obs": cfg["quality"].get("outlier_min_obs", 5),
        "outlier_min_state_markets": cfg["quality"].get("outlier_min_state_markets", 3),
        "outlier_rule": cfg["quality"].get("outlier_rule", "temporal_and_cross_section"),
        "zero_min_max_as_missing": cfg["quality"].get("zero_min_max_as_missing", True),
        "persistent_low_log_ratio": low["log_ratio"],
        "persistent_low_min_rows": low["min_rows_per_series"],
        "persistent_low_min_share": low["min_share_of_series"],
        "include_suspect_low": cfg["quality"].get("include_suspect_low", False),
        "analysis_period": cfg["analysis"]["period"],
        "road_factor": geo["road_factor"],
        "max_pair_km": geo["max_pair_km"],
        "spread_radius_km": geo["spread_radius_km"],
        "near_radius_km": access["near_radius_km"],
        "trapped_max_markets": access["trapped_max_markets"],
        "trapped_max_price_index": access["trapped_max_price_index"],
        "min_gain_abs": opp["min_gain_abs"],
        "min_gain_pct": opp["min_gain_pct"],
        "scenarios": opp["scenarios"],
        "crash_horizon_days": crash["horizon_days"],
        "crash_lookback_days": crash["lookback_days"],
        "crash_drop_ratio": crash["drop_ratio"],
    }


def ensure_profile() -> None:
    """profiles.yml is gitignored; the committed example reads everything from env vars."""
    profile = DBT_DIR / "profiles.yml"
    if not profile.exists():
        shutil.copy(DBT_DIR / "profiles.example.yml", profile)


def run_dbt(args: list[str]) -> int:
    """Extra `--vars '{...}'` given on the command line are MERGED over the settings vars
    (dbt itself would let the last --vars flag replace all the others)."""
    ensure_profile()
    args = list(args)
    extra: dict = {}
    if "--vars" in args:
        i = args.index("--vars")
        extra = yaml.safe_load(args[i + 1]) or {}
        del args[i : i + 2]
    dbt = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    cmd = [str(dbt), *args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if args and args[0] in {"build", "run", "test", "seed", "compile", "ls", "show"}:
        cmd += ["--vars", json.dumps({**dbt_vars(), **extra})]
    return subprocess.call(cmd)
