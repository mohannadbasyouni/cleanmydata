"""CLI entrypoint for cleanmydata using Typer."""

import os
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from cleanmydata.clean import clean_data
from cleanmydata.constants import EXIT_GENERAL_ERROR, EXIT_SUCCESS
from cleanmydata.context import AppContext, map_exception_to_exit_code
from cleanmydata.logging import configure_logging_json
from cleanmydata.utils.io import read_data

app = typer.Typer(
    name="cleanmydata",
    help="CleanMyData - A CLI data cleaning tool for automated cleaning of messy datasets",
)
console = Console()


def _emit_error(message: str) -> None:
    typer.secho(message, fg="red", err=True)


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
    ctx = AppContext.create(
        quiet=quiet,
        silent=silent,
        verbose=verbose,
        log_to_file=log,
    )
    quiet_mode = ctx.mode in {"quiet", "silent"}
    silent_mode = ctx.mode == "silent"
    configure_logging_json(level="ERROR" if quiet_mode else "INFO")

    def emit_info(message: str) -> None:
        if quiet_mode:
            return
        typer.secho(message, fg="green")

    try:
        df = read_data(Path(path))
    except Exception as exc:
        _emit_error(f"Error loading dataset: {exc}")
        raise typer.Exit(code=map_exception_to_exit_code(exc)) from exc

    if df.empty:
        _emit_error("Failed to load dataset or file is empty.")
        raise typer.Exit(code=EXIT_GENERAL_ERROR)

    if ctx.verbose and not quiet_mode:
        console.rule("[bold]Original Data Preview[/bold]", style="white")

        preview = df.head(2)
        table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)

        for col in preview.columns:
            table.add_column(col, overflow="fold")

        for _, row in preview.iterrows():
            table.add_row(*[str(v)[:80] for v in row.values])

        console.print(table)
        console.print(f"[dim]Rows:[/dim] {df.shape[0]:,}   [dim]Columns:[/dim] {df.shape[1]}\n")

    try:
        cleaned_df, summary = clean_data(
            df,
            verbose=ctx.verbose,
            log=log,
            dataset_name=os.path.basename(path),
        )
    except Exception as exc:
        _emit_error(str(exc))
        raise typer.Exit(code=map_exception_to_exit_code(exc)) from exc

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

    if silent_mode:
        raise typer.Exit(code=EXIT_SUCCESS)
    if quiet_mode:
        typer.echo(output_path)
    else:
        emit_info(f"Cleaned data saved as '{output_path}'")

    raise typer.Exit(code=EXIT_SUCCESS)


if __name__ == "__main__":
    app()
