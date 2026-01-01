"""CLI entrypoint for cleanmydata using Typer."""

import json
import os
from pathlib import Path

import typer
from pydantic import ValidationError as PydanticValidationError
from rich import box
from rich.table import Table
from typer.core import TyperGroup

from cleanmydata.clean import clean_data
from cleanmydata.cli_config import CLIConfig
from cleanmydata.constants import (
    EXIT_GENERAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_IO_ERROR,
    EXIT_SUCCESS,
)
from cleanmydata.context import AppContext, map_exception_to_exit_code
from cleanmydata.exceptions import DependencyError, ValidationError
from cleanmydata.logging import configure_logging_json
from cleanmydata.recipes import load_recipe
from cleanmydata.utils.io import read_data
from cleanmydata.validation.schema import validate_df_with_yaml


class DefaultCommandGroup(TyperGroup):
    """Typer group with a default command when none is provided."""

    default_command = "clean"

    def resolve_command(self, ctx, args):
        if self.default_command:
            if not args:
                args = [self.default_command]
            elif args[0] not in self.commands:
                args = [self.default_command, *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="cleanmydata",
    help="CleanMyData - A CLI data cleaning tool for automated cleaning of messy datasets",
    cls=DefaultCommandGroup,
)
recipe_app = typer.Typer(name="recipe", help="Validate and inspect cleaning recipes")


def _format_error_message(error: Exception | str) -> str:
    if isinstance(error, ValidationError) and isinstance(error.__cause__, PydanticValidationError):
        return _format_error_message(error.__cause__)
    if isinstance(error, PydanticValidationError):
        fragments: list[str] = []
        for err in error.errors():
            location = ".".join(str(part) for part in err.get("loc", ()) if part != "__root__")
            msg = err.get("msg", "").strip()
            if location:
                fragments.append(f"{location}: {msg}")
            elif msg:
                fragments.append(msg)
        detail = "; ".join(fragments).strip()
        if detail:
            return f"Invalid input: {detail}"
    return str(error)


def _emit_error(ctx: AppContext | None, error: Exception | str) -> None:
    message = _format_error_message(error)
    console = ctx.get_console(stderr=True) if ctx else AppContext.create().get_console(stderr=True)
    console.print(f"Error: {message}", soft_wrap=False, overflow="ignore", no_wrap=True)


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
    recipe: Path | None = typer.Option(
        None, "--recipe", help="Path to recipe YAML file with cleaning defaults"
    ),
    schema: Path | None = typer.Option(
        None,
        "--schema",
        help="Path to a YAML schema for validation (requires cleanmydata[schema])",
    ),
    outliers: str | None = typer.Option(
        None,
        "--outliers",
        case_sensitive=False,
        help="Outlier handling strategy: cap, remove, or none",
    ),
    normalize_cols: bool | None = typer.Option(
        None,
        "--normalize-cols/--no-normalize-cols",
        help="Normalize column names (true/false)",
    ),
    clean_text: bool | None = typer.Option(
        None, "--clean-text/--no-clean-text", help="Enable text cleaning"
    ),
    auto_outlier_detect: bool | None = typer.Option(
        None,
        "--auto-outlier-detect/--no-auto-outlier-detect",
        help="Automatically detect outliers",
    ),
):
    """Clean a messy dataset."""
    base_ctx = AppContext.create(
        quiet=bool(quiet or False),
        silent=bool(silent or False),
        verbose=bool(verbose or False),
        log_to_file=bool(log or False),
    )
    try:
        cli_config = CLIConfig.from_sources(
            cli_args={
                "path": path,
                "output": output,
                "verbose": verbose,
                "quiet": quiet,
                "silent": silent,
                "log": log,
                "outliers": CLIConfig._parse_outliers(outliers) if outliers else None,
                "normalize_cols": normalize_cols,
                "clean_text": clean_text,
                "auto_outlier_detect": auto_outlier_detect,
            },
            config_path=config,
            environ=os.environ,
            recipe_path=recipe,
        )
        cleaning_config = cli_config.to_cleaning_config()
    except FileNotFoundError as exc:
        _emit_error(base_ctx, exc)
        raise typer.Exit(code=EXIT_IO_ERROR) from exc
    except (PydanticValidationError, ValidationError) as exc:
        _emit_error(base_ctx, exc)
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
        ctx.get_console().print(message, soft_wrap=False, overflow="ignore", no_wrap=True)

    try:
        df = read_data(Path(cli_config.path))
    except Exception as exc:
        _emit_error(ctx, f"Error loading dataset: {exc}")
        raise typer.Exit(code=map_exception_to_exit_code(exc)) from exc

    if df.empty:
        _emit_error(ctx, "Failed to load dataset or file is empty.")
        raise typer.Exit(code=EXIT_GENERAL_ERROR)

    if schema:
        try:
            validate_df_with_yaml(df, Path(schema))
        except FileNotFoundError as exc:
            _emit_error(ctx, exc)
            raise typer.Exit(code=EXIT_IO_ERROR) from exc
        except DependencyError as exc:
            _emit_error(ctx, exc)
            raise typer.Exit(code=EXIT_GENERAL_ERROR) from exc
        except ValidationError as exc:
            _emit_error(ctx, exc)
            raise typer.Exit(code=EXIT_INVALID_INPUT) from exc

    if ctx.verbose and not quiet_mode:
        console = ctx.get_console()
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
        _emit_error(ctx, exc)
        raise typer.Exit(code=map_exception_to_exit_code(exc)) from exc

    if cleaned_df.empty:
        _emit_error(ctx, "No data cleaned — dataset is empty or invalid.")
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
        ctx.get_console().print(str(output_path), soft_wrap=False, overflow="ignore", no_wrap=True)
    else:
        emit_info(f"Cleaned data saved as '{output_path}'")

    raise typer.Exit(code=EXIT_SUCCESS)


@recipe_app.command("validate")
def recipe_validate(path: Path):
    """Validate a recipe file without running cleaning."""

    ctx = AppContext.create()
    try:
        recipe = load_recipe(path)
    except FileNotFoundError as exc:
        _emit_error(ctx, exc)
        raise typer.Exit(code=EXIT_IO_ERROR) from exc
    except (PydanticValidationError, ValidationError) as exc:
        _emit_error(ctx, exc)
        raise typer.Exit(code=EXIT_INVALID_INPUT) from exc

    ctx.get_console().print(f"Recipe valid: {recipe.name}", soft_wrap=False)
    raise typer.Exit(code=EXIT_SUCCESS)


@recipe_app.command("show")
def recipe_show(path: Path):
    """Show a normalized view of a recipe file."""

    ctx = AppContext.create()
    try:
        recipe = load_recipe(path)
    except FileNotFoundError as exc:
        _emit_error(ctx, exc)
        raise typer.Exit(code=EXIT_IO_ERROR) from exc
    except (PydanticValidationError, ValidationError) as exc:
        _emit_error(ctx, exc)
        raise typer.Exit(code=EXIT_INVALID_INPUT) from exc

    normalized = recipe.model_dump(exclude_none=True)
    rendered = json.dumps(normalized, sort_keys=True, indent=2)
    ctx.get_console().print(rendered)
    raise typer.Exit(code=EXIT_SUCCESS)


app.add_typer(recipe_app, name="recipe")


if __name__ == "__main__":
    app()
