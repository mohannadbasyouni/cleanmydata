"""CLI entrypoint for cleanmydata using Typer."""

import json
import os
from pathlib import Path
from typing import NoReturn

import typer
from pydantic import ValidationError as PydanticValidationError
from rich import box
from rich.table import Table
from typer.core import TyperGroup

from cleanmydata.cleaning import clean_data
from cleanmydata.cli_config import CLIConfig
from cleanmydata.config import CleaningConfig
from cleanmydata.constants import (
    EXIT_SUCCESS,
)
from cleanmydata.context import AppContext, map_exception_to_exit_code
from cleanmydata.exceptions import DependencyError, ValidationError
from cleanmydata.recipes import load_recipe, save_recipe
from cleanmydata.utils.io import read_data, write_data
from cleanmydata.utils.logging import configure_logging_json
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


def _split_dependency_error_and_hint(message: str) -> tuple[str, str | None]:
    """
    Split a dependency error message into a primary line and an optional hint line.

    Example:
      "X. Install with: pip install 'cleanmydata[excel]'" ->
        ("X.", "pip install 'cleanmydata[excel]'")
    """
    marker = "Install with:"
    if marker not in message:
        return message, None
    before, after = message.split(marker, 1)
    primary = before.strip().rstrip(".") + "."
    hint = after.strip()
    return primary, hint or None


def _emit_error(ctx: AppContext | None, error: Exception | str, *, hint: str | None = None) -> None:
    message = _format_error_message(error)
    derived_hint = hint
    if derived_hint is None:
        # Support both DependencyError instances and wrapped strings like
        # "Error loading dataset: ... Install with: pip install ..."
        message, derived_hint = _split_dependency_error_and_hint(message)
    if derived_hint is None and isinstance(error, FileNotFoundError):
        derived_hint = "Check that the path exists and is readable."

    console = ctx.get_console(stderr=True) if ctx else AppContext.create().get_console(stderr=True)
    console.print(f"Error: {message}", soft_wrap=False, overflow="ignore", no_wrap=True)
    if derived_hint:
        console.print(f"Hint: {derived_hint}", soft_wrap=False, overflow="ignore", no_wrap=True)


def _cli_exit(code: int, *, exc: Exception | None = None) -> NoReturn:
    if exc is None:
        raise typer.Exit(code=code)
    raise typer.Exit(code=code) from exc


def _cli_fail(
    ctx: AppContext | None,
    *,
    error: Exception | str,
    exc_for_code: Exception | None = None,
    hint: str | None = None,
) -> NoReturn:
    _emit_error(ctx, error, hint=hint)
    code_exc: Exception
    if exc_for_code is not None:
        code_exc = exc_for_code
    elif isinstance(error, Exception):
        code_exc = error
    else:
        code_exc = RuntimeError(str(error))
    _cli_exit(
        map_exception_to_exit_code(code_exc),
        exc=exc_for_code or (error if isinstance(error, Exception) else None),
    )


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
    profile: bool | None = typer.Option(
        None,
        "--profile/--no-profile",
        help="Enable lightweight profiling metadata in the returned summary",
    ),
):
    """Clean a messy dataset."""
    base_ctx = AppContext.create(
        quiet=bool(quiet or False),
        silent=bool(silent or False),
        verbose=bool(verbose or False),
        log_to_file=bool(log or False),
    )
    cli_overrides: dict[str, object] = {}
    cli_provided_keys: set[str] = set()

    if path is not None:
        cli_overrides["path"] = path
        cli_provided_keys.add("path")
    if output is not None:
        cli_overrides["output"] = output
        cli_provided_keys.add("output")
    if verbose is not None:
        cli_overrides["verbose"] = verbose
        cli_provided_keys.add("verbose")
    if quiet is not None:
        cli_overrides["quiet"] = quiet
        cli_provided_keys.add("quiet")
    if silent is not None:
        cli_overrides["silent"] = silent
        cli_provided_keys.add("silent")
    if log is not None:
        cli_overrides["log"] = log
        cli_provided_keys.add("log")
    if outliers is not None:
        cli_overrides["outliers"] = CLIConfig._parse_outliers(outliers)
        cli_provided_keys.add("outliers")
    if normalize_cols is not None:
        cli_overrides["normalize_cols"] = normalize_cols
        cli_provided_keys.add("normalize_cols")
    if clean_text is not None:
        cli_overrides["clean_text"] = clean_text
        cli_provided_keys.add("clean_text")
    if auto_outlier_detect is not None:
        cli_overrides["auto_outlier_detect"] = auto_outlier_detect
        cli_provided_keys.add("auto_outlier_detect")
    if profile is not None:
        cli_overrides["profile"] = profile
        cli_provided_keys.add("profile")

    try:
        cli_config = CLIConfig.from_sources(
            cli_args=cli_overrides,
            config_path=config,
            environ=os.environ,
            recipe_path=recipe,
            cli_provided_keys=cli_provided_keys,
        )
        cleaning_config = cli_config.to_cleaning_config()
    except (FileNotFoundError, PydanticValidationError, ValidationError) as exc:
        _cli_fail(base_ctx, error=exc, exc_for_code=exc)

    ctx = AppContext.create(
        quiet=cli_config.quiet,
        silent=cli_config.silent,
        verbose=cli_config.verbose,
        log_to_file=cli_config.log,
        config=cleaning_config,
    )
    configure_logging_json(level="ERROR" if ctx.quiet_mode else "INFO")

    def emit_info(message: str) -> None:
        if ctx.quiet_mode:
            return
        ctx.get_console().print(message, soft_wrap=False, overflow="ignore", no_wrap=True)

    try:
        df = read_data(Path(cli_config.path))
    except Exception as exc:
        _cli_fail(ctx, error=f"Error loading dataset: {exc}", exc_for_code=exc)

    if df.empty:
        _cli_fail(ctx, error="Failed to load dataset or file is empty.")

    if schema:
        try:
            validate_df_with_yaml(df, Path(schema))
        except (FileNotFoundError, DependencyError, ValidationError) as exc:
            _cli_fail(ctx, error=exc, exc_for_code=exc)

    if ctx.verbose and not ctx.quiet_mode:
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
            profile=cleaning_config.profile,
            log=cli_config.log,
            dataset_name=Path(cli_config.path).name,
        )
    except Exception as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)

    if cleaned_df.empty:
        _cli_fail(ctx, error="No data cleaned — dataset is empty or invalid.")

    filename = os.path.basename(cli_config.path)
    name, ext = os.path.splitext(filename)
    output_path = cli_config.output or Path("data") / f"{name}_cleaned{ext}"

    # Ensure output directory exists
    output_dir = output_path.parent if output_path.parent.as_posix() else Path(".")
    os.makedirs(output_dir, exist_ok=True)

    try:
        write_data(cleaned_df, output_path)
    except Exception as exc:
        _cli_fail(ctx, error=f"Error writing cleaned dataset: {exc}", exc_for_code=exc)

    if ctx.silent_mode:
        _cli_exit(EXIT_SUCCESS)
    if ctx.quiet_mode:
        ctx.get_console().print(str(output_path), soft_wrap=False, overflow="ignore", no_wrap=True)
    else:
        emit_info(f"Cleaned data saved as '{output_path}'")

    _cli_exit(EXIT_SUCCESS)


@recipe_app.command("validate")
def recipe_validate(path: Path):
    """Validate a recipe file without running cleaning."""

    ctx = AppContext.create()
    try:
        load_recipe(path)
    except FileNotFoundError as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)
    except (PydanticValidationError, ValidationError) as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)

    ctx.get_console().print("Recipe valid", soft_wrap=False)
    _cli_exit(EXIT_SUCCESS)


@recipe_app.command("show")
def recipe_show(path: Path):
    """Show a normalized view of a recipe file."""

    ctx = AppContext.create()
    try:
        recipe = load_recipe(path)
    except FileNotFoundError as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)
    except (PydanticValidationError, ValidationError) as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)

    normalized = {
        "outliers": "none" if recipe.outliers is None else recipe.outliers,
        "normalize_cols": recipe.normalize_cols,
        "clean_text": recipe.clean_text,
        "auto_outlier_detect": recipe.auto_outlier_detect,
    }
    rendered = json.dumps(normalized, sort_keys=True, indent=2)
    ctx.get_console().print(rendered)
    _cli_exit(EXIT_SUCCESS)


@recipe_app.command("save")
def recipe_save(
    output_yaml: Path = typer.Argument(..., help="Output recipe YAML path"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Optional YAML config file to source defaults from"
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
    """Save current config options as a recipe YAML file."""
    ctx = AppContext.create()
    allowed_keys = {"outliers", "normalize_cols", "clean_text", "auto_outlier_detect"}
    merged: dict[str, object] = {}

    try:
        if config:
            yaml_data = CLIConfig._load_yaml_config(config)
            extra = set(yaml_data) - allowed_keys
            if extra:
                raise ValidationError(
                    f"Config file contains unsupported recipe keys: {sorted(extra)}"
                )
            merged.update(yaml_data)

        env_data = CLIConfig._load_env_vars(os.environ)
        merged.update({k: v for k, v in env_data.items() if k in allowed_keys})

        if outliers is not None:
            merged["outliers"] = CLIConfig._parse_outliers(outliers)
        if normalize_cols is not None:
            merged["normalize_cols"] = normalize_cols
        if clean_text is not None:
            merged["clean_text"] = clean_text
        if auto_outlier_detect is not None:
            merged["auto_outlier_detect"] = auto_outlier_detect

        cleaning_config = CleaningConfig(**merged)
        save_recipe(cleaning_config, output_yaml)
    except (FileNotFoundError, IsADirectoryError, ValidationError) as exc:
        _cli_fail(ctx, error=exc, exc_for_code=exc)

    ctx.get_console().print(str(output_yaml), soft_wrap=False, overflow="ignore", no_wrap=True)
    _cli_exit(EXIT_SUCCESS)


@recipe_app.command("load")
def recipe_load(
    recipe_yaml: Path = typer.Argument(..., help="Recipe YAML path"),
    input_file: Path = typer.Argument(..., help="Input dataset path"),
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
    """Apply a recipe to a dataset (equivalent to clean --recipe)."""
    clean(
        path=str(input_file),
        output=output,
        verbose=verbose,
        quiet=quiet,
        silent=silent,
        log=log,
        config=config,
        recipe=recipe_yaml,
        schema=schema,
        outliers=outliers,
        normalize_cols=normalize_cols,
        clean_text=clean_text,
        auto_outlier_detect=auto_outlier_detect,
        profile=None,
    )


app.add_typer(recipe_app, name="recipe")


if __name__ == "__main__":
    app()
