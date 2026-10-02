"""Run dbt with .env loaded and config/settings.yaml passed as --vars.

python -m mandipulse dbt build
python -m mandipulse dbt test --select fact_daily_price
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from mandipulse.config import PROJECT_ROOT, get_settings  # importing config loads .env

DBT_DIR = PROJECT_ROOT / "dbt" / "mandipulse"


def dbt_vars() -> dict:
    cfg = get_settings()
    bounds = cfg["quality"]["unit_bounds_per_qtl"]
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
    }


def ensure_profile() -> None:
    """profiles.yml is gitignored; the committed example reads everything from env vars."""
    profile = DBT_DIR / "profiles.yml"
    if not profile.exists():
        shutil.copy(DBT_DIR / "profiles.example.yml", profile)


def run_dbt(args: list[str]) -> int:
    ensure_profile()
    dbt = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    cmd = [str(dbt), *args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if args and args[0] in {"build", "run", "test", "seed", "compile", "ls", "show"}:
        cmd += ["--vars", json.dumps(dbt_vars())]
    return subprocess.call(cmd)
