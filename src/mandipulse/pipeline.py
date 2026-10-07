"""End-to-end refresh: archive -> Postgres -> dbt -> ml scores -> exports (spec Phase 6).

    python -m mandipulse pipeline                 # full refresh from data/raw/kaggle
    python -m mandipulse pipeline --skip-ml       # no trained models (e.g. synthetic sample)
    python -m mandipulse pipeline --snapshot      # also refresh the committed app snapshot

Steps run in order and stop at the first failure (non-zero exit). Every step is logged with its
duration to the console and to logs/pipeline_<timestamp>.log.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime

from mandipulse.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
log = logging.getLogger("mandipulse.pipeline")


class StepFailed(RuntimeError):
    """A pipeline step returned a failure (e.g. dbt exit code != 0)."""


def _setup_logging() -> str:
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    for handler in (logging.StreamHandler(), logging.FileHandler(path, encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return path.relative_to(PROJECT_ROOT).as_posix()


def step_load(source_glob: str | None) -> None:
    """Load the archive (or the given files) into raw.mandi_prices."""
    from mandipulse.db import get_engine
    from mandipulse.ingest.load import load_kaggle

    glob = (PROJECT_ROOT / source_glob).as_posix() if source_glob else None
    for key, value in load_kaggle(get_engine(), parquet_glob=glob).items():
        log.info("    %s: %s", key, value)


def step_ml_schema() -> None:
    """Create the ml.* tables if missing."""
    from mandipulse.ml.score import init_schema

    init_schema()


def _dbt(*args: str) -> None:
    from mandipulse.dbt_runner import run_dbt

    code = run_dbt(list(args))
    if code != 0:
        raise StepFailed(f"dbt {' '.join(args)} exited with code {code}")


def step_score() -> None:
    """Score the latest dates with the trained models."""
    from mandipulse.ml.score import score_all

    for table, n in score_all().items():
        log.info("    ml.%s: %s rows", table, n)


def step_export(snapshot: bool) -> None:
    """Write the Power BI and app exports (and optionally the app snapshot)."""
    from mandipulse.export import export_all, write_app_snapshot

    manifest = export_all(progress=lambda msg: log.info("  %s", msg.strip()))
    log.info("    %d files, %.1f MB parquet", len(manifest), manifest["parquet_mb"].sum())
    if snapshot:
        log.info("    app snapshot -> %s", write_app_snapshot())


def run_pipeline(
    source_glob: str | None = None, skip_ml: bool = False, snapshot: bool = False
) -> int:
    """Run every step; return 0 on success, 1 on the first failure (logged with its traceback)."""
    log_path = _setup_logging()
    steps: list[tuple[str, Callable[[], None]]] = [
        ("load raw prices", lambda: step_load(source_glob)),
        ("create ml tables (if missing)", step_ml_schema),
        ("dbt build (staging, flags, star schema, marts + tests)", lambda: _dbt("build")),
    ]
    if not skip_ml:
        steps += [
            ("ml score (latest dates, trained models from models/)", step_score),
            ("dbt test ml outputs", lambda: _dbt("test", "--select", "source:ml")),
        ]
    steps.append(("export (Power BI + app datasets)", lambda: step_export(snapshot)))

    log.info("pipeline start: %d steps; log file %s", len(steps), log_path)
    t0 = time.perf_counter()
    for i, (name, func) in enumerate(steps, start=1):
        log.info("[%d/%d] %s", i, len(steps), name)
        t = time.perf_counter()
        try:
            func()
        except Exception:
            log.exception("[%d/%d] FAILED: %s", i, len(steps), name)
            log.error("pipeline stopped after %.0f s", time.perf_counter() - t0)
            return 1
        log.info("[%d/%d] done in %.0f s", i, len(steps), time.perf_counter() - t)
    log.info("pipeline finished OK in %.0f s", time.perf_counter() - t0)
    return 0
