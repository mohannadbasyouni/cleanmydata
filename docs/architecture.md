# CleanMyData architecture

## Overview

CleanMyData is a library-first data cleaning toolkit with an optional CLI. The codebase separates:

- **CLI boundary concerns**: parsing inputs, merging config sources, exit codes, and user-facing output.
- **Core cleaning concerns**: deterministic data transformations on a pandas `DataFrame`.
- **Optional features**: enabled via extras and guarded by runtime dependency checks.

This doc focuses on the modules involved in the CLI cleaning path and the supported extension seams.

## Module overview

### `cleanmydata/cli.py`

Typer-based CLI entrypoint. Responsibilities:

- Parse CLI arguments and options.
- Build a validated `CLIConfig` via `CLIConfig.from_sources(...)`.
- Convert to core `CleaningConfig` (`cli_config.to_cleaning_config()`).
- Read input via `utils.io.read_data(...)`.
- Optionally validate input data with `validation.schema.validate_df_with_yaml(...)`.
- Invoke the core cleaning pipeline `clean.clean_data(...)`.
- Write output via `utils.io.write_data(...)` (supports CSV, Excel, Parquet).
- Map exceptions to stable exit codes (via `context.map_exception_to_exit_code(...)`).

### `cleanmydata/cli_config.py`

Pydantic model that represents CLI-facing configuration (`CLIConfig`). Responsibilities:

- Validate input/output paths and file extensions against `constants.SUPPORTED_FORMATS`.
- Merge configuration from multiple sources with clear precedence:
  - recipe YAML (optional) → CLI YAML config (optional) → environment variables → CLI args
- Convert validated CLI options into the core `CleaningConfig` dataclass.

### `cleanmydata/recipes.py`

Recipe schema and loader. Responsibilities:

- Load a recipe YAML file into a validated `Recipe` model (Pydantic).
- Provide a `cleaning_options()` method returning only cleaning-relevant fields (used by
  `CLIConfig.from_sources(...)` as the lowest-precedence defaults layer).

### `cleanmydata/validation/schema.py`

Pandera-backed schema validation (optional). Responsibilities:

- Parse a YAML schema into a validated spec (`SchemaSpec`, `ColumnSpec`, `CheckSpec`).
- Build a `pandera.DataFrameSchema` and validate a `DataFrame`.
- Provide helpful, bounded error messages (`ValidationError`) and dependency guidance
  (`DependencyError` when `pandera` is not installed).

### `cleanmydata/utils/io.py`

Core I/O utilities. Responsibilities:

- `read_data(path)`: read `.csv` (core), `.xlsx/.xlsm` (requires `cleanmydata[excel]`), and
  `.parquet` (requires `cleanmydata[parquet]`). Explicitly rejects `.xls`.
- `write_data(df, path)`: symmetric writer for the same formats and the same optional extras.
- `clean_file(input_path, output_path, config=...)`: convenience API that reads, cleans via
  `clean.clean_data`, and writes using `write_data`.

### `cleanmydata/context.py`

CLI execution context (`AppContext`). Responsibilities:

- Encapsulate CLI output mode (`normal` / `quiet` / `silent`) and verbosity flags.
- Provide cached `rich.console.Console` instances for stdout/stderr.
- Centralize exception→exit code mapping via `map_exception_to_exit_code(...)`.

### Core cleaning modules

The core pipeline lives in the package and is intentionally usable without the CLI stack:

- **`cleanmydata/clean.py`**: `clean_data(...)` orchestrates the sequential cleaning steps:
  remove duplicates → normalize column names (optional) → clean text (optional) →
  standardize formats → handle outliers (optional) → fill missing values.
- **`cleanmydata/config.py`**: `CleaningConfig` dataclass defining core cleaning options and
  validation (`CleaningConfig.validate()`).
- **`cleanmydata/exceptions.py`**: typed exceptions (`DependencyError`, `DataLoadError`,
  `ValidationError`, etc.) used across layers for predictable error handling.
- **`cleanmydata/constants.py`**: supported formats and default values used to keep CLI and core
  defaults aligned.

## Data flow

The primary “clean a file from the CLI” flow is:

**CLI → `CLIConfig` → `CleaningConfig` → `read_data` → (optional schema validation) → `clean_data`
→ write output**

Concretely:

1. `cleanmydata/cli.py` parses arguments.
2. `CLIConfig.from_sources(...)` merges inputs (recipe/YAML/env/CLI) and validates them.
3. `cli_config.to_cleaning_config()` produces the core `CleaningConfig`.
4. `utils.io.read_data(...)` loads the dataset into a pandas `DataFrame`.
5. If `--schema` is provided, `validation.schema.validate_df_with_yaml(...)` validates the input
   `DataFrame` against a YAML schema (requires `cleanmydata[schema]`).
6. `clean.clean_data(...)` performs the cleaning pipeline and returns `(cleaned_df, summary)`.
7. The CLI writes the cleaned data via `utils.io.write_data(...)`.

## Optional dependency strategy

CleanMyData keeps the core install lightweight and uses **extras** for optional features. The
strategy is consistent across the repo:

- **Package extras** are defined in `pyproject.toml` under `[project.optional-dependencies]`.
  - `cleanmydata[cli]`: Typer/Rich/Pydantic/YAML (CLI experience)
  - `cleanmydata[excel]`: `openpyxl` for `.xlsx/.xlsm`
  - `cleanmydata[parquet]`: `pyarrow` for `.parquet`
  - `cleanmydata[schema]`: `pandera` for YAML schema validation
- **Runtime guards**: optional modules are imported inside the functions that need them.
  - Missing optional dependencies raise `DependencyError` with an install hint (e.g.
    `pip install -e ".[cli,excel]"` for the CLI or `pip install -e ".[excel]"` for the library-only path).
- **Tests** use `pytest.importorskip(...)` for optional stacks and explicitly test the
  “missing dependency” error paths (e.g. schema and parquet).

## Testing strategy (overview)

The repo uses `pytest` (configured in `pyproject.toml`) with unit-leaning tests that cover:

- **Configuration correctness**:
  - `tests/test_config.py` validates `CleaningConfig` defaults and validation rules.
  - `tests/test_cli.py` validates `CLIConfig` merging/precedence and CLI exit code behavior.
- **I/O correctness and optional dependency behavior**:
  - `tests/test_io.py` covers CSV basics, Parquet round-trip (when available), and missing-engine
    behavior for Parquet; it also enforces the `.xls` rejection contract.
- **Schema validation**:
  - `tests/test_validation.py` exercises YAML schema parsing, checks, and missing-`pandera`
    behavior.
- **Smoke coverage**:
  - `tests/test_smoke.py` validates top-level imports and a basic `clean_data` run.

When adding features, prefer:

- unit tests for new behavior at the module boundary you’re changing (I/O vs config vs schema),
- and one “integration-ish” CLI test only when behavior is observable via CLI flags/exit codes.
