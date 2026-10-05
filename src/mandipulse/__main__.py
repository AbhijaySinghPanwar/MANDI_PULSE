"""Command-line entrypoint: python -m mandipulse <command>."""

import typer

from mandipulse.config import PROJECT_ROOT, get_settings

app = typer.Typer(help="Mandi Pulse pipeline commands.", no_args_is_help=True)


@app.command("profile-kaggle")
def profile_kaggle(
    check_csv: bool = typer.Option(False, help="Also count rows in the CSV copy (slow, ~6.5 GB)."),
) -> None:
    """Profile the Kaggle archive with DuckDB; write results to reports/tables/phase0/."""
    from mandipulse.profiling import run_profile

    run_profile(check_csv=check_csv)


@app.command("load")
def load(
    source_glob: str = typer.Option(
        None, help="Load these files instead of the archive (Parquet or CSV), e.g. the CI fixture."
    ),
) -> None:
    """Load the in-scope Kaggle slice into Postgres raw.mandi_prices (idempotent)."""
    from mandipulse.db import get_engine
    from mandipulse.ingest.load import load_kaggle

    glob = (PROJECT_ROOT / source_glob).as_posix() if source_glob else None
    stats = load_kaggle(get_engine(), parquet_glob=glob)
    for key, value in stats.items():
        typer.echo(f"{key:>14}: {value}")


@app.command("reconcile")
def reconcile() -> None:
    """Compare raw.mandi_prices row counts with the Phase 0 profile."""
    from mandipulse.ingest.reconcile import OUT
    from mandipulse.ingest.reconcile import reconcile as _reconcile

    result = _reconcile()
    typer.echo(f"wrote {OUT.relative_to(OUT.parents[3]).as_posix()}")
    typer.echo(
        f"rows: profile={result.n_rows_profile.sum()} raw={result.n_rows_raw.sum()} "
        f"cells with diff != 0: {(result['diff'] != 0).sum()}"
    )


@app.command("aliases")
def aliases() -> None:
    """Build data/reference/market_aliases.csv from the raw market names in Postgres."""
    from mandipulse.ingest.market_aliases import ALIASES_CSV, build_aliases_from_db

    df = build_aliases_from_db()
    typer.echo(
        f"wrote {ALIASES_CSV.name}: {len(df)} raw names -> "
        f"{df.groupby(['state', 'district', 'market_canonical']).ngroups} canonical markets"
    )
    typer.echo(df["rule"].value_counts().to_string())
    typer.echo(df["review_decision"].replace("", "-").value_counts().to_string())


@app.command("geocode")
def geocode(
    retry: list[str] = typer.Option(  # noqa: B008
        [], help="Redo cached markets with this geo_precision (repeatable), e.g. not_found."
    ),
) -> None:
    """Geocode canonical markets (resumable; cached in data/reference/market_geo.csv)."""
    import pandas as pd

    from mandipulse.geo import geocode as g

    g.ensure_overrides_file()
    markets = g.canonical_markets()
    g.geocode_markets(
        markets,
        g.nominatim_geocoder(get_settings()["geo"]["min_delay_s"]),
        retry=frozenset(retry),
        progress=typer.echo,
    )
    geo = g.load_market_geo()
    # The cache may hold names that later reviews merged away; report current markets only.
    current = pd.DataFrame(markets, columns=["state", "district", "market"])
    geo = geo.merge(current, on=["state", "district", "market"])
    report = g.coverage_report(geo)
    out = PROJECT_ROOT / "reports" / "tables" / "phase1" / "geocode_coverage.csv"
    report.to_csv(out, index=False)
    typer.echo(report.to_string(index=False))


@app.command("dbt", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def dbt(ctx: typer.Context) -> None:
    """Run dbt in dbt/mandipulse with .env loaded and settings.yaml passed as --vars."""
    from mandipulse.dbt_runner import run_dbt

    raise typer.Exit(run_dbt(ctx.args))


@app.command("queries")
def queries(
    folder: str,
    only: str = typer.Option(None, help="Glob of query names to run, e.g. 'sanity_*'."),
) -> None:
    """Run analysis/queries/<folder>/*.sql against Postgres -> reports/tables/<folder>/."""
    from mandipulse.queries import run_folder

    for path in run_folder(folder, only):
        typer.echo(f"wrote {path.relative_to(PROJECT_ROOT).as_posix()}")


@app.command("data-dictionary")
def data_dictionary() -> None:
    """Write docs/DATA_DICTIONARY.md from the dbt mart docs and live Postgres column types."""
    from mandipulse.data_dictionary import OUT, write

    write()
    typer.echo(f"wrote {OUT.relative_to(PROJECT_ROOT).as_posix()}")


@app.command("export")
def export() -> None:
    """Write Power BI exports and the app's parquet datasets to exports/ (+ manifest)."""
    from mandipulse.export import export_all

    m = export_all(progress=typer.echo)
    typer.echo(f"wrote {len(m)} files, {m['parquet_mb'].sum():.1f} MB parquet")


ml_app = typer.Typer(help="Machine learning: train, explain, score (spec 9).", no_args_is_help=True)
app.add_typer(ml_app, name="ml")


@ml_app.command("train-all")
def ml_train_all() -> None:
    """Train + evaluate Model A (forecast), B (crash), C (clusters); SHAP plots; save artifacts."""
    from mandipulse.ml.cluster import run_clustering
    from mandipulse.ml.explain import explain_all
    from mandipulse.ml.train_crash import train_crash
    from mandipulse.ml.train_forecast import train_forecast

    typer.echo("Model A: price forecast")
    a = train_forecast()["walk_forward"]
    typer.echo(
        f"  best baseline {a['best_baseline']}; "
        f"MAE improvement {a['mae_improvement_vs_best_baseline_pct']}%"
    )
    typer.echo("Model B: crash warning")
    b = train_crash()["verdict"]
    typer.echo(
        f"  beats seasonal rule: all={b['all']['beats_seasonal_rule']}, "
        f"December={b['december']['beats_seasonal_rule']}, "
        f"other={b['other_months']['beats_seasonal_rule']}"
    )
    typer.echo("Model C: clustering")
    c = run_clustering()
    typer.echo(
        f"  k={c['chosen_k']}; suspect series by cluster: {c['suspect_series']['by_cluster']}"
    )
    typer.echo("SHAP")
    explain_all()


@ml_app.command("train-forecast")
def ml_train_forecast() -> None:
    """Model A only."""
    from mandipulse.ml.train_forecast import train_forecast

    a = train_forecast()["walk_forward"]
    typer.echo(
        f"  MAE improvement vs {a['best_baseline']}: {a['mae_improvement_vs_best_baseline_pct']}%"
    )


@ml_app.command("train-crash")
def ml_train_crash() -> None:
    """Model B only."""
    from mandipulse.ml.train_crash import train_crash

    typer.echo(str(train_crash()["verdict"]))


@ml_app.command("cluster")
def ml_cluster() -> None:
    """Model C only."""
    from mandipulse.ml.cluster import run_clustering

    c = run_clustering()
    typer.echo(
        f"  k={c['chosen_k']}; suspect series by cluster: {c['suspect_series']['by_cluster']}"
    )


@ml_app.command("explain")
def ml_explain() -> None:
    """SHAP plots + rankings for Models A and B."""
    from mandipulse.ml.explain import explain_all

    explain_all()


@ml_app.command("report")
def ml_report() -> None:
    """Render reports/ML_REPORT.md from the saved metrics files."""
    from mandipulse.ml.report import render

    typer.echo(f"wrote {render()}")


@ml_app.command("validate-forecast")
def ml_validate_forecast(
    coverage_only: bool = typer.Option(
        False, help="Only recompute test coverage with the saved calibration (no retraining)."
    ),
) -> None:
    """Model A objective check + band calibration on Nov 2024 - Apr 2025 (pre-test window)."""
    from mandipulse.ml.validate_forecast import recalibrate_test_coverage, run_validation

    m = recalibrate_test_coverage() if coverage_only else run_validation()
    typer.echo(f"  winner: {m['winner_objective']}; L1 vs L2 MAE {m['l1_vs_l2_mae_pct']}%")
    c = m["calibration"]["test_may_oct_2025"]
    typer.echo(f"  test band coverage before {c['before']['all']}% -> after {c['after']['all']}%")


@ml_app.command("logistic-weights")
def ml_logistic_weights() -> None:
    """Standardised logistic-regression weights for the crash model (Methodology page)."""
    from mandipulse.ml.train_crash import logistic_weights

    typer.echo(logistic_weights().head(10).to_string(index=False))


@ml_app.command("score")
def ml_score() -> None:
    """Score the latest available dates into ml.price_forecast, ml.crash_risk, ml.market_cluster."""
    from mandipulse.ml.score import score_all

    for table, n in score_all().items():
        typer.echo(f"  ml.{table}: {n} rows")


@ml_app.command("init-schema")
def ml_init_schema() -> None:
    """Create the (empty) ml.* tables."""
    from mandipulse.ml.score import init_schema

    init_schema()
    typer.echo("ml schema ready")


@app.command("version")
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version as _v

    typer.echo(_v("mandipulse"))


if __name__ == "__main__":
    app()
