# CLI Reference

## CLI Overview

- **Command name:** `cleanmydata`
- **Primary command:** `clean` (invoked as `cleanmydata clean`; `clean` is the default when no subcommand is provided)

## Commands

### clean

- **Syntax:** `cleanmydata clean [OPTIONS] [PATH]`
- **Description:** Reads the dataset at `PATH` (defaulting to `.csv` if no extension is supplied) and writes a cleaned dataset to disk. Supported input formats include `.csv`, `.xlsx`, `.xlsm`, and `.parquet` (Excel/parquet support requires the optional extras `cleanmydata[excel]` or `cleanmydata[parquet]`).
- **Options:**
  - `--output`, `-o <FILE>` – Explicit output path (defaults to `data/<input_name>_cleaned.<ext>`).
  - `--config`, `-c <FILE>` – YAML file that supplies CLI options (see Config precedence).
  - `--recipe <FILE>` – Recipe YAML that provides cleaning defaults; merged before CLI arguments.
  - `--schema <FILE>` – YAML schema for validation steps (requires `cleanmydata[schema]`).
  - `--verbose/--no-verbose` – Show detailed cleaning logs. Automatically disabled when `--quiet` or `--silent` is supplied.
  - `--quiet/--no-quiet` – Suppress info/progress output (errors still go to stderr). Automatically disables `--verbose`.
  - `--silent/--no-silent` – No stdout output except for errors.
  - `--log/--no-log` – Deprecated no-op flag (JSON structured logs are always emitted to stdout/stderr).
  - `--outliers <cap|remove|none>` – Outlier strategy (defaults to `cap`; case-insensitive). `none` disables outlier handling.
  - `--normalize-cols/--no-normalize-cols` – Normalize column names (defaults to enabled).
  - `--clean-text/--no-clean-text` – Enable/disable text cleaning (defaults to enabled).
  - `--auto-outlier-detect/--no-auto-outlier-detect` – Automatically detect outliers (defaults to enabled).

- **Output modes:**
  - **Normal:** Default when neither `--quiet` nor `--silent` is set; prints status messages and final summary.
  - **Quiet:** Suppresses status/progress output but still prints the resulting file path.
  - **Silent:** Suppresses all stdout output; only errors are emitted to stderr.

- **When schema validation runs:** Validation occurs immediately after loading the dataset and before any cleaning actions.

#### Schema contract (reality-first)

- **Supported schema file format**: YAML (loaded via `yaml.safe_load`).
- **Schema shape**:
  - Top-level mapping with optional `name` and required `columns` mapping.
  - `columns.<col_name>` supports: `dtype` (`int|float|str|bool|datetime`), `nullable` (default false), `required` (default true), and optional `checks` list.
  - Supported checks: `in_range` (`min`/`max`, numeric dtypes only), `isin` (list), `regex` (string dtype only).
- **CLI surface**: `cleanmydata clean --schema PATH` (also available via `cleanmydata recipe load ... --schema PATH`).
- **UX contract**:
  - Errors are printed to stderr as `Error: ...` with an optional `Hint: ...` line.
  - Exit codes are determined by the centralized mapping in `cleanmydata.context.map_exception_to_exit_code(...)`.
- **Failure modes**:
  - **Missing optional dependency (`pandera`)**: exit code `2` with an install hint (`pip install "cleanmydata[schema]"`).
  - **Schema file missing/unreadable**: exit code `3` (`FileNotFoundError`), with a path hint.
  - **Invalid YAML**: exit code `2` (`ValidationError`) with `Invalid YAML in schema file: ...`.
  - **Invalid schema structure**: exit code `2` (`ValidationError`) with either `Schema file must contain a top-level mapping` or a pydantic-derived `Invalid input: ...` message.
  - **Data does not match schema**: exit code `2` with `Schema validation failed: ...` including a short summary of failure cases.

### recipe group

- **Commands:**
  - `cleanmydata recipe validate PATH` – Validates the recipe YAML and reports success.
  - `cleanmydata recipe show PATH` – Prints the normalized recipe content as JSON.
- **Note:** Neither command runs any cleaning; they only inspect or validate recipe files.

## Config precedence

`cleanmydata` merges settings in the following order (lowest to highest priority):

- Recipe defaults (`--recipe`)
- `--config` YAML file (`cleanmydata clean --config path/to/file.yaml`)
- Environment variables (`CLEANMYDATA_*`)
- Explicit CLI arguments (`--output`, `--outliers`, etc.)

The highest-priority source overrides earlier ones.

## Environment variables

| Variable | Maps to | Notes |
| --- | --- | --- |
| `CLEANMYDATA_PATH` | `path` | Input dataset (supports `.csv`, `.xlsx`, `.xlsm`, `.parquet`). |
| `CLEANMYDATA_OUTPUT` | `output` | Output file path (must include supported extension). |
| `CLEANMYDATA_VERBOSE` | `verbose` | Boolean (`1/true/yes/on` → true, `0/false/no/off` → false). |
| `CLEANMYDATA_QUIET` | `quiet` | Boolean (`quiet` supersedes `verbose`). |
| `CLEANMYDATA_SILENT` | `silent` | Boolean (supersedes `quiet` and `verbose`). |
| `CLEANMYDATA_LOG` | `log` | Boolean (deprecated flag, still parsed). |
| `CLEANMYDATA_OUTLIERS` | `outliers` | Accepts `cap`, `remove`, `none` (case-insensitive; `none` disables outlier handling). |
| `CLEANMYDATA_NORMALIZE_COLS` | `normalize_cols` | Boolean (defaults to true). |
| `CLEANMYDATA_CLEAN_TEXT` | `clean_text` | Boolean (defaults to true). |
| `CLEANMYDATA_AUTO_OUTLIER_DETECT` | `auto_outlier_detect` | Boolean (defaults to true). |

- **Boolean parsing rules:** The CLI accepts `1`, `true`, `yes`, or `on` for true; `0`, `false`, `no`, or `off` for false (case-insensitive, surrounding whitespace is ignored).
- **Outliers environment values:** `cap`, `remove`, or `none` (case-insensitive). Any other value raises validation errors.

## Exit codes

| Code | Meaning | Example |
| --- | --- | --- |
| `0` | Success | Clean completed, output written to disk. |
| `1` | General error | Unexpected errors (e.g., empty dataset in the CLI path). |
| `2` | Invalid input | CLI validation failure, schema validation errors, or missing dependencies (optional extras). |
| `3` | I/O error | Input/config/recipe file not found or unreadable. |

## Examples

- **CSV clean:** `cleanmydata clean data/messy_data_10k.csv` (writes `data/messy_data_10k_cleaned.csv`).
- **Excel clean:** `cleanmydata clean data/messy_data_10k.xlsx` (requires `cleanmydata[excel]`; default output is `data/messy_data_10k_cleaned.xlsx`).
- **Parquet clean:** `cleanmydata clean data/messy_data_10k.parquet` (requires `cleanmydata[parquet]`; default output is `data/messy_data_10k_cleaned.parquet`).
- **Recipe usage:** `cleanmydata clean --recipe recipes/daily-clean.yaml data/daily.csv` (recipe-provided defaults merge before CLI overrides).
- **Schema failure example:** `cleanmydata clean --schema schema/mismatch.yaml data/messy_data_10k.csv` (runs schema validation after loading; exits with `2` on failure).
