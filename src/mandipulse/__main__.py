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


@app.command("version")
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version as _v

    typer.echo(_v("mandipulse"))


if __name__ == "__main__":
    app()
