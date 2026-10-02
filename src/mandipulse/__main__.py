"""Command-line entrypoint: python -m mandipulse <command>."""

import typer

app = typer.Typer(help="Mandi Pulse pipeline commands.", no_args_is_help=True)


@app.command("profile-kaggle")
def profile_kaggle(
    check_csv: bool = typer.Option(False, help="Also count rows in the CSV copy (slow, ~6.5 GB)."),
) -> None:
    """Profile the Kaggle archive with DuckDB; write results to reports/tables/phase0/."""
    from mandipulse.profiling import run_profile

    run_profile(check_csv=check_csv)


@app.command("version")
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version as _v

    typer.echo(_v("mandipulse"))


if __name__ == "__main__":
    app()
