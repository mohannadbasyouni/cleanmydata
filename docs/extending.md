# Extending CleanMyData safely

This guide documents the supported extension seams in the current repo. The goal is to add new
capabilities while keeping:

- CLI behavior predictable (validation, error messages, exit codes)
- core library behavior usable without the CLI extras
- optional dependencies isolated behind extras + runtime guards

## Adding a new file format (step-by-step)

CleanMyData’s file format support is enforced in three places:

1) **Format allow-list** (`cleanmydata/constants.py`)

- Add your extension (e.g. `".jsonl"`) to the appropriate set and ensure it’s included in
  `SUPPORTED_FORMATS`.
- Decide whether it is a **core** format or requires an **optional extra**.

2) **Reader/writer implementation** (`cleanmydata/utils/io.py`)

- Update `read_data(path: Path)`:
  - Add a new `elif suffix == "...":` branch that returns a `pandas.DataFrame`.
  - If the implementation requires a non-core dependency, import it inside the branch and raise
    `DependencyError` with a clear install hint on `ImportError`.
- Update `write_data(df: DataFrame, path: Path)` similarly for symmetry.

3) **CLI path validation** (`cleanmydata/cli_config.py`)

- `CLIConfig` validates the input and output suffixes against `SUPPORTED_FORMATS`.
- Once `constants.SUPPORTED_FORMATS` includes your new extension, the CLI will accept it.

### Where to add tests

- **Reader/writer tests**: `tests/test_io.py`
  - Add a “read succeeds” test (if feasible with a small fixture) and/or a “write succeeds” test.
  - If the format requires an optional dependency, follow the existing pattern:
    - use `pytest.importorskip(...)` for round-trip tests when the dependency is available
    - add a test that forces an `ImportError` and asserts a `DependencyError` with the expected
      install hint
- **CLI validation tests (if needed)**: `tests/test_cli.py`
  - Add a test that the CLI rejects unknown extensions and accepts the new extension once added.

## Adding a new cleaning option

Cleaning options live in both the **core** configuration and the **CLI-facing** configuration.
To add a new option safely, wire it through all layers explicitly.

### Step-by-step

1) **Add to core config** (`cleanmydata/config.py`)

- Add a new field to `CleaningConfig` with a sensible default.
- Extend `CleaningConfig.validate()` if the field needs validation.
- Update `tests/test_config.py` to cover the new default and any validation behavior.

2) **Add to the core pipeline** (`cleanmydata/clean.py`)

- Add a keyword argument to `clean_data(...)` (and/or thread the config field through).
- Implement the behavior in the pipeline as a discrete step (ideally as a helper function).
- Keep behavior deterministic and make sure exceptions propagate (the CLI maps them to exit codes).

3) **Expose via CLI config** (`cleanmydata/cli_config.py`)

- Add the field to `CLIConfig` so it can be set via config sources.
- If you want environment-variable support, extend the `env_map` in `_load_env_vars(...)`.
- Ensure `to_cleaning_config()` maps the new field into the returned `CleaningConfig`.

4) **Expose via the CLI command** (`cleanmydata/cli.py`)

- Add a Typer option to the `clean` command signature.
- Pass the resolved option through to `clean_data(...)` (via the derived `CleaningConfig`).

5) **(Optional) Support recipes** (`cleanmydata/recipes.py`)

If the new option should be settable via recipe YAML:

- Add the field to the `Recipe` model (Pydantic).
- Include it in `Recipe.cleaning_options()` by adding it to the `allowed_fields` set.
- Add or update tests in `tests/test_recipes.py`.

### Where to add tests

- **Core behavior**: `tests/test_smoke.py` (for a minimal “does it run?” coverage) and/or create a
  focused unit test in an existing test module depending on what you changed (for example, new
  config validation belongs in `tests/test_config.py`).
- **CLI wiring / precedence**: `tests/test_cli.py`
  - The existing tests already validate precedence: recipe → YAML → env → CLI overrides.
  - Add one test ensuring your new option is correctly passed into `clean_data(...)` (the pattern
    already exists via monkeypatching `cli_module.clean_data` and capturing kwargs).

## Adding a new schema check

Schema checks are defined as a small, explicit allow-list in `cleanmydata/validation/schema.py`.
To add a new check, extend the spec model and translate it into a Pandera `Check`.

### Step-by-step

1) **Extend the check specification** (`cleanmydata/validation/schema.py`)

- Add a new optional field to `CheckSpec` (similar to `in_range`, `isin`, `regex`).
- Update `CheckSpec._validate_exactly_one` so exactly one check type is provided.
- Update `CheckSpec.to_pandera(...)` to translate the new check into a `pa.Check...` call.
- If the check is dtype-specific, update `ColumnSpec._validate_checks` with the correct guardrails.

2) **Add tests for YAML + runtime behavior**

- Add a passing and/or failing case in `tests/test_validation.py`:
  - Create a schema YAML snippet that uses the new check.
  - Validate a small `DataFrame` and assert it raises `ValidationError` when expected.

### Where to add tests

- **Schema parsing + validation**: `tests/test_validation.py` (primary place)
- **CLI integration (optional)**: `tests/test_cli.py`
  - Only needed if you want to ensure `--schema` surfaces failures with the expected exit code and
    stderr message; there is already a test for schema-validation failure behavior.
