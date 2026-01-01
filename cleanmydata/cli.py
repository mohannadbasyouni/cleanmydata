"""CLI entrypoint for cleanmydata using Typer."""

import os
from pathlib import Path

import typer
from pydantic import ValidationError as PydanticValidationError
from rich import box
from rich.console import Console
from rich.table import Table

from cleanmydata.clean import clean_data
from cleanmydata.cli_config import CLIConfig
from cleanmydata.constants import (
    EXIT_GENERAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_IO_ERROR,
    EXIT_SUCCESS,
)
from cleanmydata.context import AppContext, map_exception_to_exit_code
from cleanmydata.exceptions import ValidationError
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
    path: str | None = typer.Argument(
        None, help=".csv (default), .xlsx/.xlsm (requires cleanmydata[excel])"
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Output file name (default: original_cleaned.csv)"
    ),
    verbose: bool | None = typer.Option(
        None, "--verbose/--no-verbose", "-v/-V", help="Show detailed cleaning logs"
    ),
    quiet: bool | None = typer.Option(
        None, "--quiet/--no-quiet", help="Suppress info/progress output"
    ),
    silent: bool | None = typer.Option(
        None, "--silent/--no-silent", help="No stdout output (errors still to stderr)"
    ),
    log: bool | None = typer.Option(
        None,
        "--log/--no-log",
        help="Deprecated: no-op (structured JSON logs are always emitted to stdout/stderr)",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to YAML config file with CLI options"
    ),
):
    """Clean a messy dataset."""
    try:
        cli_config = CLIConfig.from_sources(
            cli_args={
                "path": path,
                "output": output,
                "verbose": verbose,
                "quiet": quiet,
                "silent": silent,
                "log": log,
            },
            config_path=config,
            environ=os.environ,
        )
        cleaning_config = cli_config.to_cleaning_config()
    except FileNotFoundError as exc:
        _emit_error(str(exc))
        raise typer.Exit(code=EXIT_IO_ERROR) from exc
    except (PydanticValidationError, ValidationError) as exc:
        _emit_error(str(exc))
        raise typer.Exit(code=EXIT_INVALID_INPUT) from exc

    ctx = AppContext.create(
        quiet=cli_config.quiet,
        silent=cli_config.silent,
        verbose=cli_config.verbose,
        log_to_file=cli_config.log,
        config=cleaning_config,
    )
    quiet_mode = ctx.mode in {"quiet", "silent"}
    silent_mode = ctx.mode == "silent"
    configure_logging_json(level="ERROR" if quiet_mode else "INFO")

    def emit_info(message: str) -> None:
        if quiet_mode:
            return
        typer.secho(message, fg="green")

    try:
        df = read_data(Path(cli_config.path))
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
            outliers=cleaning_config.outliers,
            normalize_cols=cleaning_config.normalize_cols,
            clean_text=cleaning_config.clean_text,
            categorical_mapping=cleaning_config.categorical_mapping,
            auto_outlier_detect=cleaning_config.auto_outlier_detect,
            verbose=cleaning_config.verbose,
            log=cli_config.log,
            dataset_name=Path(cli_config.path).name,
        )
    except Exception as exc:
        _emit_error(str(exc))
        raise typer.Exit(code=map_exception_to_exit_code(exc)) from exc

    if cleaned_df.empty:
        _emit_error("No data cleaned — dataset is empty or invalid.")
        raise typer.Exit(code=EXIT_GENERAL_ERROR)

    filename = os.path.basename(cli_config.path)
    name, ext = os.path.splitext(filename)
    output_path = cli_config.output or Path("data") / f"{name}_cleaned{ext}"

    # Ensure output directory exists
    output_dir = output_path.parent if output_path.parent.as_posix() else Path(".")
    os.makedirs(output_dir, exist_ok=True)

    cleaned_df.to_csv(output_path, index=False)

    if silent_mode:
        raise typer.Exit(code=EXIT_SUCCESS)
    if quiet_mode:
        typer.echo(str(output_path))
    else:
        emit_info(f"Cleaned data saved as '{output_path}'")

    raise typer.Exit(code=EXIT_SUCCESS)


if __name__ == "__main__":
    app()
