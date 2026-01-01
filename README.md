# CleanMyData

## Project overview
CleanMyData is a CLI-first data cleaning tool that turns messy CSV, Excel, or Parquet tables into standardized datasets with sensible defaults and optional presets. It is aimed at data engineers and analysts who want repeatable cleanup workflows without writing boilerplate pandas code. CleanMyData supports CSV, Excel (`.xlsx`/`.xlsm`), and Parquet (`.parquet`) for both input and output.

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

By default the CLI writes to `data/<input_name>_cleaned.<ext>` (preserving the input format) and prints status messages. Pass `--output` (or `-o`) to write to a different path or change the format (e.g., convert CSV to Parquet). Input files may be `.csv`, `.xlsx`, `.xlsm`, or `.parquet` (Excel/parquet support requires the corresponding extras).

- Quiet mode (`--quiet`) suppresses progress/info output but still prints the final path when the job succeeds.
- Silent mode (`--silent`) suppresses all stdout (only errors appear on stderr), making it easy to script around exit codes.

CleanMyData uses exit codes to signal outcomes: `0` for success, `1` for general errors, `2` for invalid input (including missing dependencies and validation issues), and `3` for I/O failures.

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
- [Installation](docs/install.md)
- [Quickstart](docs/quickstart.md)
- [Configuration](docs/config.md)
- [Supported Formats](docs/formats.md)
- [CLI Reference](docs/cli.md)
- [Contributing](docs/contributing.md)
- [Architecture Overview](docs/architecture.md)

## Troubleshooting
- If the CLI mentions `Excel support is not installed` or `Parquet support is not installed`, rerun pip with `pip install -e ".[cli,excel]"` or `pip install -e ".[cli,parquet]"` (or install the library-only extras if you do not need the CLI). Schema errors prompt `pip install -e ".[cli,schema]"`.
- CI may emit `ddtrace` warnings when optional tracing hooks are discovered; those warnings are non-fatal and can be ignored unless you are explicitly enabling tracing.
