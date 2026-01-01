# CleanMyData

## Project overview
CleanMyData is a CLI-first data cleaning tool that turns messy CSV, Excel, or Parquet tables into standardized datasets with sensible defaults and optional presets. It is aimed at data engineers and analysts who want repeatable cleanup workflows without writing boilerplate pandas code. CleanMyData always supports CSV input/output out of the box; install `cleanmydata[excel]` to add `.xlsx`/`.xlsm` support and `cleanmydata[parquet]` to add `.parquet` handling.

## Installation

CleanMyData is currently distributed from this repository rather than PyPI. Install the package in editable mode to get access to the library and its CLI extras.

### Library-only install
```bash
pip install -e .
```

### CLI install
```bash
pip install -e ".[cli]"
```

### Optional extras
- `pip install -e ".[cli,excel]"` – adds Excel input support (`.xlsx`/`.xlsm`) via `openpyxl`.
- `pip install -e ".[cli,parquet]"` – adds Parquet input support via `pyarrow`.
- `pip install -e ".[cli,schema]"` – adds schema validation via `pandera`.
- `pip install -e ".[all]"` – installs every optional dependency (API, storage, CLI, Excel, Parquet, schema, tooling).
- Alternatively install directly from GitHub with a template like `pip install "PROJECT @ git+https://github.com/<user>/<repo>.git"` and add extras as needed.

## Quickstart (CLI)
Clean a CSV with the default settings:

```bash
cleanmydata clean data/messy_data_10k.csv
```

By default the CLI writes to `data/<input_name>_cleaned.csv` and prints status messages. Pass `--output` (or `-o`) to write to a different path; the CLI always emits CSV, so prefer `.csv` output files even if the input was Excel or Parquet. Input files may still be `.csv`, `.xlsx`, `.xlsm`, or `.parquet` (Excel/parquet support requires the corresponding extras). The library itself exposes `utils.io.write_data(...)`, which supports CSV, Excel, and Parquet output formats, but the CLI path currently calls `DataFrame.to_csv(...)` so scripts relying on multi-format output should call `write_data` directly.

- Quiet mode (`--quiet`) suppresses progress/info output but still prints the final path when the job succeeds.
- Silent mode (`--silent`) suppresses all stdout (only errors appear on stderr), making it easy to script around exit codes.

CleanMyData uses exit codes to signal outcomes: `0` for success, `1` for general errors (missing dependencies, empty datasets, etc.), `2` for validation issues, and `3` for I/O failures such as missing files or unreadable configs.

## Recipes (YAML)
Recipes are YAML-based cleaning presets that provide defaults for the CLI's cleaning options (`outliers`, `normalize_cols`, `clean_text`, `auto_outlier_detect`, and `categorical_mapping`). Recipes let teams capture standard behavior and reuse it across runs.

Minimal recipe example:

```yaml
name: nightly-clean
description: Standard nightly cleanup for ingest batches
outliers: remove
normalize_cols: true
clean_text: true
auto_outlier_detect: true
```

Validate and inspect recipes with:

- `cleanmydata recipe validate recipes/nightly-clean.yaml`
- `cleanmydata recipe show recipes/nightly-clean.yaml`

Apply a recipe by passing it to the main clean command (recipe defaults merge before CLI overrides):

```bash
cleanmydata clean --recipe recipes/nightly-clean.yaml data/batch.csv
```

## Config precedence
- Recipe defaults (via `--recipe`)
- `--config` YAML file (`cleanmydata clean --config path/to/file.yaml`)
- Environment variables (`CLEANMYDATA_*`)
- Explicit CLI arguments (`--output`, `--outliers`, etc.)

## Schema validation
Pass `--schema path/to/schema.yaml` to validate the loaded dataset before cleaning. Schema validation requires the `cleanmydata[schema]` extra so Pandera is available.

Minimal schema snippet:

```yaml
name: customer-schema
columns:
  id:
    dtype: int
  email:
    dtype: str
    nullable: false
  signup_date:
    dtype: datetime
    nullable: true
```

Validation runs immediately after the CSV/Excel/Parquet file loads and aborts with exit code `2` on failures.

## Documentation
- [CLI reference](docs/cli.md)
- [Architecture overview](docs/architecture.md)
- [Extending CleanMyData](docs/extending.md)

## Troubleshooting
- If the CLI mentions `Excel support is not installed` or `Parquet support is not installed`, rerun pip with `pip install -e ".[cli,excel]"` or `pip install -e ".[cli,parquet]"` (or install the library-only extras if you do not need the CLI). Schema errors prompt `pip install -e ".[cli,schema]"`.
- CI may emit `ddtrace` warnings when optional tracing hooks are discovered; those warnings are non-fatal and can be ignored unless you are explicitly enabling tracing.
