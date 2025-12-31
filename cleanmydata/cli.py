"""CLI entrypoint for cleanmydata using Typer."""

import os
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from cleanmydata.clean import clean_data
from cleanmydata.constants import (
    EXIT_GENERAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_IO_ERROR,
    EXIT_SUCCESS,
)
from cleanmydata.exceptions import DataLoadError, DependencyError, ValidationError
from cleanmydata.logging import configure_logging_json
from cleanmydata.utils.io import read_data

app = typer.Typer(
    name="cleanmydata",
    help="CleanMyData - A CLI data cleaning tool for automated cleaning of messy datasets",
)
console = Console()


def _exit_code_for_exception(exc: BaseException) -> int:
    if isinstance(exc, (FileNotFoundError, DataLoadError)):
        return EXIT_IO_ERROR
    if isinstance(exc, (ValidationError, DependencyError)):
        return EXIT_INVALID_INPUT
    return EXIT_GENERAL_ERROR


def _emit_error(message: str) -> None:
    typer.echo(message, err=True)


@app.command()
def clean(
    path: str = typer.Argument(
        ..., help=".csv (default), .xlsx/.xlsm (requires cleanmydata[excel])"
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Output file name (default: original_cleaned.csv)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed cleaning logs"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress info/progress output"),
    silent: bool = typer.Option(
        False, "--silent", help="No stdout output (errors still to stderr)"
    ),
    log: bool = typer.Option(
        False,
        "--log",
        help="Deprecated: no-op (structured JSON logs are always emitted to stdout/stderr)",
    ),
):
    """Clean a messy dataset."""
    quiet = quiet or silent
    configure_logging_json(level="ERROR" if quiet else "INFO")

    def emit_info(message: str) -> None:
        if quiet:
            return
        typer.echo(message)

    try:
        df = read_data(Path(path))
    except Exception as e:
        _emit_error(f"Error loading dataset: {e}")
        raise typer.Exit(code=_exit_code_for_exception(e)) from e

    if df.empty:
        _emit_error("Failed to load dataset or file is empty.")
        raise typer.Exit(code=EXIT_GENERAL_ERROR)

    if verbose:
        if not quiet:
            console.rule("[bold]Original Data Preview[/bold]", style="white")

        preview = df.head(2)
        table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)

        for col in preview.columns:
            table.add_column(col, overflow="fold")

        for _, row in preview.iterrows():
            table.add_row(*[str(v)[:80] for v in row.values])

        if not quiet:
            console.print(table)
            console.print(f"[dim]Rows:[/dim] {df.shape[0]:,}   [dim]Columns:[/dim] {df.shape[1]}\n")

    try:
        cleaned_df, summary = clean_data(
            df,
            verbose=verbose,
            log=log,
            dataset_name=os.path.basename(path),
        )
    except Exception as e:
        _emit_error(str(e))
        raise typer.Exit(code=_exit_code_for_exception(e)) from e

    if cleaned_df.empty:
        _emit_error("No data cleaned — dataset is empty or invalid.")
        raise typer.Exit(code=EXIT_GENERAL_ERROR)

    filename = os.path.basename(path)
    name, ext = os.path.splitext(filename)
    output_path = output or os.path.join("data", f"{name}_cleaned{ext}")

    # Ensure output directory exists
    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True
    )

    cleaned_df.to_csv(output_path, index=False)

    if not silent:
        if quiet:
            typer.echo(output_path)
        else:
            emit_info(f"Cleaned data saved as '{output_path}'")

    raise typer.Exit(code=EXIT_SUCCESS)


if __name__ == "__main__":
    app()
