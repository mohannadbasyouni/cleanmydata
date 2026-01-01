## Phase 1.1 – Output modes contract + exit codes



### Cursor Execution Prompt



```javascript

## Task: Implement Output Modes and Exit Codes Contract (PR 1.1)



### Goal

Lock CLI output behavior and exit codes with automated tests. After this phase, CLI behavior is contractually defined and cannot regress without failing CI.



### Scope

Files allowed to modify:

- `cleanmydata/cli.py`

- `cleanmydata/constants.py` (add exit code constants)

- `tests/test_cli.py` (new file)



### Requirements



**Exit Codes (add to constants.py):**

- `EXIT_SUCCESS = 0`

- `EXIT_GENERAL_ERROR = 1`

- `EXIT_INVALID_INPUT = 2`

- `EXIT_IO_ERROR = 3`



**Output Modes (implement in cli.py):**

Add CLI options `--quiet` and `--silent` with these behaviors:

- **Normal (default):** info/progress on stdout; errors on stderr

- **Quiet (`--quiet`):** no info/progress; errors on stderr

- **Silent (`--silent`):** no stdout; errors on stderr (still returns correct non-zero exit codes)

- Silent overrides quiet if both are specified



**Exit Code Mapping (in cli.py):**

- Success → `EXIT_SUCCESS`

- FileNotFoundError → `EXIT_IO_ERROR`

- DataLoadError → `EXIT_IO_ERROR`

- ValidationError → `EXIT_INVALID_INPUT`

- DependencyError → `EXIT_INVALID_INPUT`

- All other exceptions → `EXIT_GENERAL_ERROR`



### Tests Required (tests/test_cli.py)

Use `typer.testing.CliRunner`. Create tests that verify:



1. `test_cli_success_exit_code` — valid CSV returns exit code 0

2. `test_cli_file_not_found_exit_code` — missing file returns exit code 3

3. `test_cli_invalid_format_exit_code` — unsupported format returns exit code 2

4. `test_cli_normal_mode_stdout` — normal mode prints info to stdout

5. `test_cli_normal_mode_stderr` — normal mode prints errors to stderr

6. `test_cli_quiet_mode_no_progress` — quiet mode emits nothing to stdout (except final output path)

7. `test_cli_quiet_mode_errors_stderr` — quiet mode still emits errors to stderr

8. `test_cli_silent_mode_no_stdout` — silent mode emits nothing to stdout

9. `test_cli_silent_mode_errors_stderr` — silent mode emits errors to stderr

10. `test_cli_silent_overrides_quiet` — `--silent --quiet` behaves as silent



### Constraints

- Do NOT modify core cleaning logic

- Do NOT change logging.py

- Do NOT add new dependencies

- Do NOT refactor unrelated code

- Use typer.testing.CliRunner, not subprocess



### Definition of Done

- Exit codes are defined in constants.py

- CLI uses defined exit codes correctly

- --quiet and --silent options exist and work

- All 10 tests pass

- CI remains green

```



### Notes

- Dependency: None
- Risk: Existing CLI behavior will change; ensure backwards compatibility for `--verbose`
- The exit code mapping should be centralized in one location within cli.py

---

## Phase 1.2 – Anchor modules (gap closure)



### Cursor Execution Prompt



````javascript

## Task: Complete Anchor Modules (PR 1.2 gap closure)



### Goal

Add missing exception types specified in the plan. The existing anchor modules are partially complete.



### What Already Exists

- `constants.py` — has CORE_FORMATS, EXCEL_FORMATS, OUTLIER_METHODS ✓

- `exceptions.py` — has CleanMyDataError, DependencyError, DataLoadError, DataCleaningError, ValidationError ✓

- `models.py` — has CleaningResult, ValidationResult with correct success semantics ✓

- `config.py` — has CleaningConfig dataclass with .validate() ✓



### Scope

Files allowed to modify:

- `cleanmydata/exceptions.py`



### Requirements

Add two missing exception types to exceptions.py:



1. **InvalidInputError(CleanMyDataError)**

    - Raised when user provides invalid input/configuration

    - Docstring: "Raised when input data or configuration is invalid."



2. **CleanIOError(CleanMyDataError)**

    - Raised when I/O operations fail (file read/write errors)

    - Docstring: "Raised when file I/O operations fail."



### Verification

Run existing tests to confirm no regressions:

```bash

pytest tests/ -v

````

Verify imports work:

```python

from cleanmydata.exceptions import InvalidInputError, CleanIOError

```



### Constraints

- Do NOT modify existing exception classes
- Do NOT change any other files
- Do NOT add exception handling logic (that comes in later phases)
- Keep exception definitions minimal (no custom **init** unless needed)



### Definition of Done

- InvalidInputError exists in exceptions.py
- CleanIOError exists in exceptions.py
- Both inherit from CleanMyDataError
- All existing tests pass
```javascript



### Notes

- These exceptions will be used by later phases (CLI exit code mapping, I/O module)

- No other modules need to import these yet; that happens in Phase 1.1 and 1.3



---



## Phase 1.3 – I/O module + convenience API (gap closure)



### Cursor Execution Prompt



```




## Task: Add clean_file Convenience API (PR 1.3 gap closure)



### Goal

Add the missing `clean_file()` convenience function to the I/O module.

### What Already Exists

- `cleanmydata/utils/io.py` has `read_data()` and `write_data()` ✓
- Excel DependencyError with exact install hint works ✓
- Tests for CSV and Excel missing-dep exist ✓



### Scope

Files allowed to modify:

- `cleanmydata/utils/io.py`
- `tests/test_smoke.py` (add tests)



### Requirements

**Add to cleanmydata/utils/io.py:**

```javascript

def clean_file(

    input_path: Path,

    output_path: Path,

    config: CleaningConfig | None = None

) -> CleaningResult:

    """

    Convenience function: read, clean, and write a file in one call.



    Args:

        input_path: Path to input file (.csv, .xlsx, .xlsm)

        output_path: Path to output file

        config: Optional CleaningConfig; uses defaults if None



    Returns:

        CleaningResult with cleaning statistics



    Raises:

        FileNotFoundError: If input file does not exist

        DataLoadError: If file cannot be parsed

        DependencyError: If Excel support required but not installed

    """

```

Implementation:

1. Call `read_data(input_path)` to load DataFrame
2. Import and call `clean_data()` from `cleanmydata.clean` with config parameters
3. Call `write_data(df, output_path)` to save result
4. Convert the summary dict to CleaningResult and return it

**Import requirements:**

- Import CleaningConfig from cleanmydata.config
- Import CleaningResult from cleanmydata.models
- Import clean_data from cleanmydata.clean



### Tests Required (add to tests/test_smoke.py)



1. `test_clean_file_csv_happy_path` — clean_file reads CSV, cleans, writes, returns CleaningResult with rows > 0
2. `test_clean_file_with_custom_config` — clean_file accepts CleaningConfig and applies it
3. `test_clean_file_file_not_found` — clean_file raises FileNotFoundError for missing input



### Constraints

- Do NOT modify read_data or write_data
- Do NOT change clean_data signature
- Do NOT add new dependencies
- CleaningResult must be constructed from the summary dict returned by clean_data



### Definition of Done

- clean_file() exists in cleanmydata/utils/io.py
- clean_file() returns CleaningResult (not dict)
- All 3 new tests pass
- All existing tests pass
```javascript



### Notes

- Dependency: CleaningResult model must exist (it does)

- The clean_data function returns (df, summary_dict); must convert summary_dict to CleaningResult



---



## Phase 1.4 – Logging (gap closure)



### Cursor Execution Prompt



```




## Task: Verify and Document Logging Implementation (PR 1.4 gap closure)



### Goal

The logging implementation uses structlog with JSON output instead of RichHandler as originally specified. This is a valid architectural decision for production observability. Document this deviation and ensure all plan requirements are met.

### What Already Exists

- `cleanmydata/logging.py` with `get_logger()`, `configure_logging_json()`, `reset_logging_for_tests()` ✓
- Named logger "cleanmydata" used throughout ✓
- No root logger configuration in core ✓
- Tests exist for logging behavior ✓



### Scope

Files allowed to modify:

- `cleanmydata/logging.py` (docstring updates only)



### Requirements

**Verify these plan requirements are met:**

1. `get_logger()` returns named logger "cleanmydata" only — VERIFY
2. `configure_logging_json()` is CLI-only (not called in core modules) — VERIFY
3. `reset_logging_for_tests()` exists and is used by tests — VERIFY
4. No root logger config anywhere in core — VERIFY
5. Repeated calls do not duplicate handlers — VERIFY

**Add module docstring clarification:**Update the module docstring in logging.py to explicitly state:

- This module uses structlog with JSON output for Datadog compatibility
- RichHandler was considered but JSON logging chosen for production observability
- CLI calls configure_logging_json() at startup; library users should not call it



### Verification

Run logging tests:

```bash

pytest tests/test_logging.py -v

```

Grep to confirm no core module calls configure_logging_json:

- Only cli.py and api.py should call it



### Constraints

- Do NOT change logging behavior
- Do NOT add RichHandler
- Docstring update only



### Definition of Done

- Module docstring documents the structlog/JSON design decision
- Verification confirms all 5 requirements are met
- No functional changes
```javascript



### Notes

- This phase is essentially complete; this prompt documents the deviation and verifies compliance

- The JSON logging approach is actually better for production than RichHandler



---



## Phase 1.5 – AppContext factory + CLI wiring



### Cursor Execution Prompt



```




## Task: Implement AppContext Factory (PR 1.5)



### Goal

Create a centralized context factory for CLI wiring. The CLI should construct one AppContext and use it throughout, with exit-code mapping in one place.

### Scope

Files allowed to create:

- `cleanmydata/context.py` (new file)

Files allowed to modify:

- `cleanmydata/cli.py`
- `tests/test_cli.py` (add context tests if file exists, else create)



### Requirements

**Create cleanmydata/context.py:**

```python

@dataclass

class AppContext:

    """

    CLI execution context. Created once at CLI entry point.

    Core functions do not create or depend on this.

    """

    mode: Literal["normal", "quiet", "silent"]

    verbose: bool

    log_to_file: bool

    config: CleaningConfig



    @classmethod

    def create(

        cls,

        *,

        quiet: bool = False,

        silent: bool = False,

        verbose: bool = False,

        log_to_file: bool = False,

        config: CleaningConfig | None = None,

    ) -> "AppContext":

        """

        Factory method to create AppContext.

        Silent overrides quiet.

        """

        if silent:

            mode = "silent"

        elif quiet:

            mode = "quiet"

        else:

            mode = "normal"



        return cls(

            mode=mode,

            verbose=verbose,

            log_to_file=log_to_file,

            config=config or CleaningConfig(),

        )

```

**Add exit code mapping function to context.py:**

```python

def map_exception_to_exit_code(exc: Exception) -> int:

    """

    Map exceptions to CLI exit codes.

    Centralized mapping for consistent behavior.

    """

    from cleanmydata.constants import (

        EXIT_SUCCESS, EXIT_GENERAL_ERROR,

        EXIT_INVALID_INPUT, EXIT_IO_ERROR

    )

    from cleanmydata.exceptions import (

        DependencyError, ValidationError,

        DataLoadError, InvalidInputError, CleanIOError

    )



    if isinstance(exc, FileNotFoundError):

        return EXIT_IO_ERROR

    if isinstance(exc, (DataLoadError, CleanIOError)):

        return EXIT_IO_ERROR

    if isinstance(exc, (ValidationError, InvalidInputError, DependencyError)):

        return EXIT_INVALID_INPUT

    return EXIT_GENERAL_ERROR

```

**Modify cli.py:**

- Import AppContext from context.py
- Create AppContext.create() at CLI entry point
- Use map_exception_to_exit_code() for all exception handling
- Remove inline exit code logic



### Tests Required



1. `test_appcontext_create_defaults` — default mode is "normal"
2. `test_appcontext_silent_overrides_quiet` — silent=True, quiet=True results in mode="silent"
3. `test_appcontext_quiet_mode` — quiet=True results in mode="quiet"
4. `test_map_exception_file_not_found` — FileNotFoundError maps to EXIT_IO_ERROR
5. `test_map_exception_validation_error` — ValidationError maps to EXIT_INVALID_INPUT
6. `test_map_exception_general` — RuntimeError maps to EXIT_GENERAL_ERROR



### Constraints

- Do NOT import context.py in core modules (clean.py, config.py, models.py, etc.)
- Do NOT add Rich console creation yet (defer to Phase 7.3)
- Do NOT change core cleaning logic
- Context is CLI-only



### Definition of Done

- context.py exists with AppContext dataclass and factory
- map_exception_to_exit_code() is centralized in context.py
- cli.py uses AppContext.create() and map_exception_to_exit_code()
- All 6 tests pass
- Core modules do not import context
```javascript



### Notes

- Dependency: Phase 1.1 (exit code constants) and Phase 1.2 (exception types) should be complete

- Console creation deferred to Phase 7.3 to avoid scope creep



---



## Phase 3.1 – Core unit tests (gap closure)



### Cursor Execution Prompt



```




## Task: Complete Core Unit Tests (PR 3.1 gap closure)



### Goal

Expand test coverage for core modules to meet 90%+ coverage on critical modules.

### What Already Exists

- tests/test_smoke.py — import tests, clean_data basic, SettingWithCopyWarning regression ✓
- tests/test_logging.py — JSON format, DD context, stderr routing ✓
- tests/test_metrics.py — metrics client selection, emission ✓
- tests/test_storage.py — storage client selection, GCS operations ✓



### Scope

Files allowed to create:

- `tests/test_config.py` (new file)
- `tests/test_exceptions.py` (new file)
- `tests/test_models.py` (new file)
- `tests/test_io.py` (new file)



### Requirements

**tests/test_config.py:**

1. `test_cleaning_config_defaults` — default values are correct
2. `test_cleaning_config_validate_valid_outlier` — "cap", "remove", None are valid
3. `test_cleaning_config_validate_invalid_outlier` — invalid outlier method raises ValidationError
4. `test_cleaning_config_validate_invalid_categorical_mapping` — non-dict raises ValidationError

**tests/test_exceptions.py:**

1. `test_all_exceptions_inherit_from_base` — all custom exceptions inherit CleanMyDataError
2. `test_exception_messages` — exceptions can be raised with custom messages

**tests/test_models.py:**

1. `test_validation_result_success_no_errors` — success=True when errors=[]
2. `test_validation_result_failed_with_errors` — success=False when errors present
3. `test_validation_result_success_with_warnings` — warnings don't affect success
4. `test_cleaning_result_success_property` — success determined by errors only
5. `test_cleaning_result_to_dict` — to_dict() returns expected keys

**tests/test_io.py:**

1. `test_read_data_csv_success` — reads CSV correctly
2. `test_read_data_file_not_found` — raises FileNotFoundError
3. `test_read_data_unsupported_format` — raises DataLoadError for .txt
4. `test_read_data_xls_rejected` — raises DataLoadError for .xls with conversion hint
5. `test_write_data_csv_success` — writes CSV correctly
6. `test_write_data_xls_rejected` — raises DataLoadError for .xls



### Verification

```bash

pytest tests/test_config.py tests/test_exceptions.py tests/test_models.py tests/test_io.py -v

pytest --cov=cleanmydata --cov-report=term-missing

```

Target: 90%+ coverage on config.py, exceptions.py, models.py, utils/io.py

### Constraints

- Do NOT modify source code
- Do NOT add tests for modules not in scope (clean.py is tested elsewhere)
- Use fixtures from tests/fixtures/ where applicable



### Definition of Done

- All 4 new test files created
- All tests pass
- Coverage on config/exceptions/models/io modules is 90%+
```javascript



### Notes

- Dependency: None

- These tests lock down the anchor modules before restructuring



---



## Phase 3.2 – CLI contract tests



### Cursor Execution Prompt



```




## Task: Implement CLI Contract Tests (PR 3.2)



### Goal

Lock CLI output behavior with comprehensive contract tests using typer.testing.CliRunner. These tests prevent regression of output modes and exit codes.

### Scope

Files allowed to modify:

- `tests/test_cli.py` (expand if exists from Phase 1.1, else create)



### Requirements

**Test Output Modes:**

1. `test_cli_normal_prints_info_to_stdout` — normal mode includes info/progress on stdout
2. `test_cli_normal_prints_errors_to_stderr` — errors go to stderr in normal mode
3. `test_cli_quiet_no_progress_stdout` — quiet mode suppresses progress
4. `test_cli_quiet_errors_still_stderr` — quiet mode still emits errors to stderr
5. `test_cli_silent_empty_stdout` — silent mode produces no stdout
6. `test_cli_silent_errors_still_stderr` — silent mode still emits errors to stderr
7. `test_cli_silent_correct_exit_code_on_error` — silent mode returns correct exit codes

**Test Exit Codes:**

8. `test_cli_exit_0_on_success` — successful clean returns 0
9. `test_cli_exit_2_on_invalid_input` — unsupported format returns 2
10. `test_cli_exit_3_on_file_not_found` — missing file returns 3
11. `test_cli_exit_2_on_excel_missing_dep` — Excel without extra returns 2 (DependencyError)

**Test CSV Core Install:**

12. `test_cli_csv_works_without_extras` — CSV cleaning works with core install

**Test Excel Behavior:**

13. `test_cli_excel_without_extra_shows_install_hint` — error message includes install command



### Implementation Pattern

```python

from typer.testing import CliRunner

from cleanmydata.cli import app



runner = CliRunner()



def test_cli_exit_0_on_success(tmp_path):

    # Create test CSV

    csv_file = tmp_path / "test.csv"

    csv_file.write_text("a,b\n1,2\n")

    output_file = tmp_path / "out.csv"



    result = runner.invoke(app, [str(csv_file), "-o", str(output_file)])



    assert result.exit_code == 0

```



### Constraints

- Use CliRunner, not subprocess
- Do NOT modify cli.py in this phase
- Do NOT test internal implementation details
- Test observable behavior only (stdout, stderr, exit code)



### Definition of Done

- All 13 contract tests pass
- Tests use CliRunner exclusively
- Tests cover all output modes (normal, quiet, silent)
- Tests cover all exit codes (0, 2, 3)
- CI remains green
```javascript



### Notes

- Dependency: Phase 1.1 must be complete (output modes and exit codes implemented)

- These tests form the CLI contract that protects against regressions



---



## Phase 4.1 – Move to target structure



### Cursor Execution Prompt



```




## Task: Restructure to Target Module Layout (PR 4.1)



### Goal

Reorganize source files to match target structure. This is a mechanical refactor; no behavior changes.

### Current Structure

```javascript

cleanmydata/

├── __init__.py

├── clean.py

├── cli.py

├── config.py

├── constants.py

├── exceptions.py

├── logging.py

├── models.py

├── context.py

├── utils/

│   ├── io.py

│   └── storage.py

└── ai/

    ├── gemini.py

    └── prompts.py

```



### Target Structure

```javascript

cleanmydata/

├── __init__.py

├── cli.py                    # CLI boundary only

├── context.py                # CLI context factory

├── config.py                 # CleaningConfig

├── constants.py              # Constants

├── exceptions.py             # All exceptions

├── models.py                 # Result models

├── cleaning/                 # NEW: core cleaning logic

│   ├── __init__.py

│   └── pipeline.py          # moved from clean.py

├── validation/               # NEW: validation logic

│   └── __init__.py

├── utils/

│   ├── __init__.py

│   ├── io.py

│   ├── logging.py           # moved from cleanmydata/logging.py

│   └── storage.py

└── ai/

    ├── __init__.py

    ├── gemini.py

    └── prompts.py

```



### Scope

Files to move:

- `cleanmydata/clean.py` → `cleanmydata/cleaning/pipeline.py`
- `cleanmydata/logging.py` → `cleanmydata/utils/logging.py`

Files to create:

- `cleanmydata/cleaning/__init__.py` (re-export clean_data)
- `cleanmydata/validation/__init__.py` (empty for now)



### Requirements



1. Move clean.py to cleaning/pipeline.py
2. Create cleaning/**init**.py that exports:

    - `clean_data` from `.pipeline`
    - All individual cleaning functions (remove_duplicates, etc.)



3. Move logging.py to utils/logging.py
4. Update all imports throughout the codebase



5. Update cleanmydata/**init**.py to import from new locations



### Verification

```bash

# All existing tests must pass unchanged

pytest tests/ -v



# Import check

python -c "from cleanmydata import clean_data; from cleanmydata.cleaning import clean_data"

python -c "from cleanmydata.utils.logging import get_logger"

```



### Constraints

- Do NOT change any function signatures
- Do NOT change any behavior
- Do NOT rename functions
- Tests must pass WITHOUT modification (test behavior, not structure)
- Preserve all existing functionality



### Definition of Done

- Target directory structure matches plan
- All imports updated
- All Phase 3 tests pass unchanged
- No behavior changes
```javascript



### Notes

- Dependency: Phase 3 tests must be complete (they verify no regression)

- This is high-risk; run tests after each file move

- validation/ is created empty for future use



---



## Phase 4.2 – Stable public API exports



### Cursor Execution Prompt



```




## Task: Standardize Public API Exports (PR 4.2)



### Goal

Define the stable public API in `cleanmydata/__init__.py`. Only export what users should depend on.

### Scope

Files allowed to modify:

- `cleanmydata/__init__.py`



### Requirements

**Exports must include exactly:**

```python

from cleanmydata.cleaning import clean_data

from cleanmydata.utils.io import clean_file, read_data, write_data

from cleanmydata.config import CleaningConfig

from cleanmydata.models import CleaningResult, ValidationResult

from cleanmydata.exceptions import (

    CleanMyDataError,

    DataLoadError,

    DataCleaningError,

    DependencyError,

    ValidationError,

    InvalidInputError,

    CleanIOError,

)



__version__ = "0.1.0"



__all__ = [

    # Core functions

    "clean_data",

    "clean_file",

    "read_data",

    "write_data",

    # Configuration

    "CleaningConfig",

    # Results

    "CleaningResult",

    "ValidationResult",

    # Exceptions

    "CleanMyDataError",

    "DataLoadError",

    "DataCleaningError",

    "DependencyError",

    "ValidationError",

    "InvalidInputError",

    "CleanIOError",

    # Metadata

    "__version__",

]

```

**Version must remain 0.1.0** until API stabilization is intentional.

### Verification

```python

# All exports work

from cleanmydata import (

    clean_data, clean_file, read_data, write_data,

    CleaningConfig, CleaningResult, ValidationResult,

    CleanMyDataError, DataLoadError, DependencyError,

    __version__

)

assert __version__ == "0.1.0"

```



### Constraints

- Do NOT add exports beyond the list above
- Do NOT change **version**
- Do NOT export internal helpers (normalize_column_names, etc.)
- Do NOT export cli, context, or logging modules



### Definition of Done

- **init**.py exports exactly the specified API
- **all** lists all exports
- **version** is "0.1.0"
- All tests pass
```javascript



### Notes

- Dependency: Phase 4.1 (restructure) must be complete

- This defines the stable API surface users can depend on



---



## Phase 5.1 – Add type hints



### Cursor Execution Prompt



```




## Task: Add Type Hints to Core and Utils (PR 5.1)



### Goal

Add type hints to all public functions in core and utils modules.

### Scope

Files allowed to modify:

- `cleanmydata/cleaning/pipeline.py`
- `cleanmydata/utils/io.py`
- `cleanmydata/utils/logging.py`
- `cleanmydata/config.py`
- `cleanmydata/models.py`
- `cleanmydata/context.py`



### Requirements

**Type hint style:**

- Use `Path` from pathlib for file paths
- Use `pd.DataFrame` for dataframes
- Use `CleaningConfig` for config parameters
- Use `CleaningResult` for return types
- Use `| None` syntax (not Optional) for Python 3.10+
- Avoid complex generics

**Priority functions to annotate:**

1. `clean_data(df: pd.DataFrame, ...) -> tuple[pd.DataFrame, dict[str, Any]]`
2. `read_data(path: Path) -> pd.DataFrame`
3. `write_data(df: pd.DataFrame, path: Path) -> None`
4. `clean_file(input_path: Path, output_path: Path, config: CleaningConfig | None = None) -> CleaningResult`
5. `get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger`
6. `CleaningConfig.validate(self) -> None`
7. `AppContext.create(...) -> AppContext`
8. `map_exception_to_exit_code(exc: Exception) -> int`



### Verification

```bash

# Syntax check (no runtime errors)

python -c "import cleanmydata"



# All tests still pass

pytest tests/ -v

```



### Constraints

- Do NOT change function behavior
- Do NOT add runtime type checking
- Do NOT use TYPE_CHECKING imports unless necessary
- Prefer simple types over complex generics



### Definition of Done

- All public functions in scope have type hints
- No runtime errors from type hints
- All tests pass
```javascript



### Notes

- Dependency: Phase 4.1 (restructure) should be complete

- Type hints are documentation; mypy enforcement is Phase 5.2



---



## Phase 5.2 – Add mypy in relaxed mode



### Cursor Execution Prompt



```




## Task: Add Mypy to CI in Relaxed Mode (PR 5.2)



### Goal

Add mypy type checking to CI in a relaxed configuration that passes without blocking development.

### Scope

Files allowed to create:

- `mypy.ini` or add `[tool.mypy]` section to `pyproject.toml`

Files allowed to modify:

- `.github/workflows/ci.yml`



### Requirements

**Mypy configuration (add to pyproject.toml):**

```toml

[tool.mypy]

python_version = "3.10"

warn_return_any = true

warn_unused_ignores = true

ignore_missing_imports = true

exclude = [

    "build/",

    "tests/",

]

```

**Add CI job to .github/workflows/ci.yml:**

```yaml

  type-check:

    runs-on: ubuntu-latest

    steps:

        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5

        with:

          python-version: "3.11"

        - name: Install dependencies

        run: |

          python -m pip install --upgrade pip

          python -m pip install -e ".[dev]"

        - name: Run mypy

        run: python -m mypy cleanmydata/

```



### Verification

```bash

# Local mypy check passes

mypy cleanmydata/



# CI workflow is valid YAML

python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

```



### Constraints

- Do NOT enable strict mode
- Do NOT fail on missing stubs (ignore_missing_imports = true)
- Do NOT type-check tests directory
- Mypy must pass on current codebase



### Definition of Done

- Mypy configuration added to pyproject.toml
- CI job added for type checking
- `mypy cleanmydata/` passes locally
- CI remains green
```javascript



### Notes

- Dependency: Phase 5.1 (type hints) should be complete

- Relaxed mode means ignore_missing_imports and no strict flags

- Can be tightened later after codebase is fully typed



---



## Phase 6.1 – Tox matrix



### Cursor Execution Prompt



```




## Task: Add Tox Configuration (PR 6.1)



### Goal

Create tox.ini to run tests across Python 3.10, 3.11, and 3.12.

### Scope

Files allowed to create:

- `tox.ini`



### Requirements

**Create tox.ini:**

```ini

[tox]

envlist = py310,py311,py312

isolated_build = true



[testenv]

deps =

    pytest>=7.0.0

    pytest-cov>=4.0.0

extras = test

commands =

    pytest tests/ -v --cov=cleanmydata --cov-report=term-missing



[testenv:lint]

deps = ruff

commands =

    ruff check cleanmydata/ tests/

    ruff format --check cleanmydata/ tests/



[testenv:typecheck]

deps = mypy>=1.7.0

extras = dev

commands =

    mypy cleanmydata/

```



### Verification

```bash

# Verify tox configuration is valid

tox --listenvs



# Run specific environment (if Python version available)

tox -e py311



# Run all environments

tox

```



### Constraints

- Do NOT modify CI to use tox (optional future enhancement)
- Do NOT add environments beyond py310, py311, py312, lint, typecheck
- Use isolated_build = true for proper package isolation



### Definition of Done

- tox.ini exists with py310, py311, py312 environments
- `tox --listenvs` shows all environments
- `tox -e py311` passes (if Python 3.11 available)
- lint and typecheck environments defined
```javascript



### Notes

- Dependency: None

- tox provides local multi-version testing; CI already tests versions separately

- Developer can run `tox` locally before pushing



---



## Phase 6.2 – Security scan (Bandit)



### Cursor Execution Prompt



```




## Task: Add Bandit Security Scanning (PR 6.2)



### Goal

Add Bandit security scanning to CI as a non-blocking informational check.

### Scope

Files allowed to create:

- `.bandit` or `bandit.yaml` (configuration)

Files allowed to modify:

- `.github/workflows/ci.yml`
- `tox.ini`



### Requirements

**Create bandit configuration (.bandit or pyproject.toml section):**

```toml

# Add to pyproject.toml

[tool.bandit]

exclude_dirs = ["tests", "build"]

skips = ["B101"]  # Skip assert warnings (used in tests)

```

**Add CI job (non-blocking):**

```yaml

  security:

    runs-on: ubuntu-latest

    continue-on-error: true  # Non-blocking

    steps:

        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5

        with:

          python-version: "3.11"

        - name: Install bandit

        run: pip install bandit[toml]

        - name: Run bandit

        run: bandit -r cleanmydata/ -c pyproject.toml

```

**Add tox environment:**

```ini

[testenv:security]

deps = bandit[toml]

commands =

    bandit -r cleanmydata/ -c pyproject.toml

```



### Verification

```bash

# Local bandit check

bandit -r cleanmydata/ -c pyproject.toml



# Should report issues but not fail CI

```



### Constraints

- Must be non-blocking (continue-on-error: true)
- Do NOT fail builds on low-severity issues
- Tune skips to avoid noisy false positives
- Do NOT scan tests directory



### Definition of Done

- Bandit configuration exists
- CI job runs bandit (non-blocking)
- `bandit -r cleanmydata/` runs without errors
- No high-severity issues in output
```javascript



### Notes

- Dependency: None

- Non-blocking means CI stays green even if bandit finds issues

- Review bandit output periodically and fix real issues



---



## Phase 6.3 – Expand tests to hit coverage targets



### Cursor Execution Prompt



```




## Task: Expand Tests for Coverage Targets (PR 6.3)



### Goal

Add tests to achieve coverage targets: 70% overall, 90%+ on critical modules.

### Scope

Files allowed to modify/create:

- `tests/test_config.py`
- `tests/test_io.py`
- `tests/test_context.py`
- `tests/test_clean.py` (new)
- `tests/test_cli.py`



### Requirements

**Critical modules requiring 90%+ coverage:**

- cleanmydata/config.py
- cleanmydata/exceptions.py
- cleanmydata/models.py
- cleanmydata/utils/io.py
- cleanmydata/context.py
- cleanmydata/cli.py

**Additional tests needed:test_io.py additions:**

1. `test_read_data_empty_csv` — raises DataLoadError for empty file
2. `test_read_data_parse_error` — raises DataLoadError for malformed CSV
3. `test_write_data_permission_error` — handles permission errors gracefully

**test_context.py additions:**

4. `test_appcontext_with_custom_config` — config is preserved
5. `test_map_exception_dependency_error` — DependencyError maps to EXIT_INVALID_INPUT
6. `test_map_exception_clean_io_error` — CleanIOError maps to EXIT_IO_ERROR

**test_clean.py (new):**

7. `test_clean_data_empty_dataframe` — handles empty df gracefully
8. `test_clean_data_with_config` — respects CleaningConfig parameters
9. `test_remove_duplicates_basic` — removes exact duplicates
10. `test_normalize_column_names` — normalizes various column name formats
11. `test_handle_outliers_cap` — capping works correctly
12. `test_fill_missing_values` — fills missing values appropriately



### Verification

```bash

pytest --cov=cleanmydata --cov-report=term-missing --cov-fail-under=70



# Check critical module coverage individually

pytest --cov=cleanmydata.config --cov-report=term-missing

pytest --cov=cleanmydata.utils.io --cov-report=term-missing

```



### Constraints

- Do NOT lower coverage thresholds
- Do NOT add tests for non-critical modules just for coverage
- Focus on edge cases and error paths
- Test behavior, not implementation



### Definition of Done

- Overall coverage ≥70%
- config.py, exceptions.py, models.py, io.py, context.py, cli.py ≥90%
- All tests pass
- CI enforces coverage threshold
```javascript



### Notes

- Dependency: Phases 1-4 should be complete

- Coverage enforcement can be added to CI with `--cov-fail-under=70`



---



## Phase 7.1 – CLIConfig (Pydantic)



### Cursor Execution Prompt



```




## Task: Implement CLIConfig with Pydantic (PR 7.1)



### Goal

Create a Pydantic model for CLI configuration that validates input and converts to CleaningConfig.

### Scope

Files allowed to create:

- `cleanmydata/cli_config.py` (new)

Files allowed to modify:

- `cleanmydata/cli.py`
- `pyproject.toml` (add pydantic to cli extra if not present)
- `tests/test_cli.py`



### Requirements

**Create cleanmydata/cli_config.py:**

```python

from pydantic import BaseModel, Field, field_validator

from cleanmydata.config import CleaningConfig

from cleanmydata.constants import OUTLIER_METHODS



class CLIConfig(BaseModel):

    """

    CLI configuration validated with Pydantic.

    Used only at CLI boundary; converts to CleaningConfig for core.

    """

    input_path: str

    output_path: str | None = None

    outliers: str = Field(default="cap")

    normalize_cols: bool = True

    clean_text: bool = True

    auto_outlier_detect: bool = True

    verbose: bool = False

    quiet: bool = False

    silent: bool = False



    @field_validator("outliers")

    @classmethod

    def validate_outliers(cls, v):

        if v not in ["cap", "remove", "none"]:

            raise ValueError(f"Invalid outlier method: {v}")

        return v



    def to_cleaning_config(self) -> CleaningConfig:

        """Convert to core CleaningConfig."""

        return CleaningConfig(

            outliers=self.outliers if self.outliers != "none" else None,

            normalize_cols=self.normalize_cols,

            clean_text=self.clean_text,

            auto_outlier_detect=self.auto_outlier_detect,

            verbose=self.verbose,

        )

```

**Update cli.py:**

- Create CLIConfig from CLI arguments
- Use CLIConfig.to_cleaning_config() to get CleaningConfig
- Let Pydantic validation errors propagate (handled by exit code mapping)

**Ensure pydantic is in cli extra:**

```toml

cli = [

    "rich>=14.0.0",

    "typer>=0.9.0",

    "pydantic>=2.0.0",

]

```



### Tests Required

1. `test_cli_config_valid_creation` — valid args create CLIConfig
2. `test_cli_config_invalid_outliers` — invalid outlier raises ValidationError
3. `test_cli_config_to_cleaning_config` — conversion works correctly



### Constraints

- CLIConfig is CLI-only; core modules do NOT import it
- Do NOT add pydantic to core dependencies
- Do NOT change CleaningConfig



### Definition of Done

- CLIConfig exists with validation
- CLI uses CLIConfig
- Conversion to CleaningConfig works
- All tests pass
```javascript



### Notes

- Dependency: None

- Pydantic is already used in api.py, so this is consistent



---



## Phase 7.2 – Config precedence contract



### Cursor Execution Prompt



```




## Task: Implement Config Precedence (PR 7.2)



### Goal

Implement and test configuration precedence: CLI args > environment variables > YAML file > defaults.

### Scope

Files allowed to modify:

- `cleanmydata/cli_config.py`
- `cleanmydata/cli.py`
- `tests/test_cli.py`



### Requirements

**Precedence order (highest to lowest):**

1. CLI arguments
2. Environment variables (CLEANMYDATA_*)
3. YAML config file (--config option)
4. Defaults

**Environment variable mapping:**

- `CLEANMYDATA_OUTLIERS` → outliers
- `CLEANMYDATA_NORMALIZE_COLS` → normalize_cols (bool: "true"/"false")
- `CLEANMYDATA_CLEAN_TEXT` → clean_text (bool)
- `CLEANMYDATA_AUTO_OUTLIER_DETECT` → auto_outlier_detect (bool)
- `CLEANMYDATA_VERBOSE` → verbose (bool)

**Add to cli.py:**

- `--config PATH` option to load YAML config file
- Load env vars if CLI args not provided
- Load YAML if env vars not set

**YAML format:**

```yaml

outliers: cap

normalize_cols: true

clean_text: true

auto_outlier_detect: true

```



### Tests Required

1. `test_config_cli_overrides_env` — CLI arg takes precedence over env var
2. `test_config_env_overrides_yaml` — env var takes precedence over YAML
3. `test_config_yaml_overrides_defaults` — YAML takes precedence over defaults
4. `test_config_full_precedence_chain` — all levels work together



### Constraints

- Do NOT require PyYAML in core (only CLI)
- Do NOT change behavior when no config sources provided
- Precedence must be deterministic



### Definition of Done

- CLI args override env vars
- Env vars override YAML config
- YAML config overrides defaults
- All 4 precedence tests pass
```javascript



### Notes

- Dependency: Phase 7.1 (CLIConfig) must be complete

- Add PyYAML to cli extra in pyproject.toml



---



## Phase 7.3 – UX polish



### Cursor Execution Prompt



```




## Task: CLI UX Polish (PR 7.3)



### Goal

Ensure consistent error messages and proper mode handling across all CLI paths.

### Scope

Files allowed to modify:

- `cleanmydata/cli.py`
- `cleanmydata/context.py`
- `tests/test_cli.py`



### Requirements

**Consistent error message format:**All error messages should follow pattern:

```javascript

Error: <brief description>

  → <actionable suggestion>

```

Example:

```javascript

Error: File not found: data.csv

  → Check the file path and try again

```

**Exit handling:**

- Always use `raise typer.Exit(code=X)` for exits
- Never use `sys.exit()` directly
- Exception-to-exit-code mapping is centralized in context.py

**Mode handling consistency:**

- Quiet mode: no progress, show errors, show final output path
- Silent mode: no stdout at all, show errors on stderr, correct exit code
- Normal mode: full progress, info, and errors

**Console creation (add to context.py):**

```python

def get_console(mode: str) -> Console:

    """Get Rich console configured for output mode."""

    if mode == "silent":

        return Console(file=io.StringIO())  # Discard output

    return Console(stderr=True if mode == "quiet" else False)

```



### Tests Required

1. `test_cli_error_message_format` — error messages follow format
2. `test_cli_all_paths_use_typer_exit` — no sys.exit() calls
3. `test_cli_mode_handling_consistency` — modes behave as documented



### Constraints

- Do NOT change exit codes
- Do NOT change output mode semantics
- Focus on consistency and polish



### Definition of Done

- Error messages follow consistent format
- All exits use typer.Exit()
- Mode handling is consistent across all code paths
- Tests verify consistency
```javascript



### Notes

- Dependency: Phases 7.1 and 7.2 should be complete

- This is polish; functional behavior should already work



---



## Phase 8.1 – Parquet read/write



### Cursor Execution Prompt



```




## Task: Implement Parquet Read/Write Support (PR 8.1)



### Goal

Add parquet file support to read_data and write_data with proper DependencyError handling.

### Scope

Files allowed to modify:

- `cleanmydata/constants.py`
- `cleanmydata/utils/io.py`
- `tests/test_io.py`



### Requirements

**Update constants.py:**

```python

PARQUET_FORMATS = {".parquet"}

SUPPORTED_FORMATS = CORE_FORMATS | EXCEL_FORMATS | PARQUET_FORMATS

```

**Update read_data in io.py:**Add parquet handling:

```python

elif suffix == ".parquet":

    try:

        import pyarrow  # noqa: F401

    except ImportError as e:

        raise DependencyError(

            'Parquet support is not installed. Install with: pip install "cleanmydata[parquet]"'

        ) from e

    df = pd.read_parquet(path)

```

**Update write_data in io.py:**Add parquet handling with same DependencyError pattern.

### Tests Required

1. `test_read_data_parquet_missing_dep` — raises DependencyError with install hint
2. `test_write_data_parquet_missing_dep` — raises DependencyError with install hint
3. `test_read_data_parquet_success` — reads parquet when pyarrow installed (mark as skip if not available)
4. `test_write_data_parquet_success` — writes parquet when pyarrow installed



### Constraints

- Do NOT add pyarrow to core dependencies
- DependencyError message must include exact install command
- Follow same pattern as Excel handling



### Definition of Done

- .parquet added to SUPPORTED_FORMATS
- read_data handles .parquet files
- write_data handles .parquet files
- Missing pyarrow raises DependencyError with install hint
- All 4 tests pass
```javascript



### Notes

- Dependency: None

- parquet extra already defined in pyproject.toml



---



## Phase 8.2 – .xls explicitly rejected



### Cursor Execution Prompt



```




## Task: Verify .xls Rejection (PR 8.2)



### Goal

Verify that .xls files are explicitly rejected with a clear conversion hint.

### What Already Exists

- `utils/io.py` read_data() rejects .xls with message ✓
- `utils/io.py` write_data() rejects .xls with message ✓



### Scope

Files allowed to modify:

- `tests/test_io.py`



### Requirements

**Verify existing rejection messages include:**

- "Unsupported file format: .xls"
- "Please convert to .xlsx or .xlsm"

**Add tests:**

1. `test_read_data_xls_rejected_with_hint` — .xls raises DataLoadError with conversion hint
2. `test_write_data_xls_rejected_with_hint` — .xls raises DataLoadError with conversion hint



### Test Implementation

```python

def test_read_data_xls_rejected_with_hint(tmp_path):

    xls_file = tmp_path / "test.xls"

    xls_file.write_bytes(b"fake xls")



    with pytest.raises(DataLoadError) as exc_info:

        read_data(xls_file)



    assert ".xls" in str(exc_info.value)

    assert "convert" in str(exc_info.value).lower()

    assert ".xlsx" in str(exc_info.value)

```



### Constraints

- Do NOT change existing rejection behavior
- Tests verify current behavior is correct



### Definition of Done

- Tests verify .xls rejection includes conversion hint
- Both read and write paths tested
- All tests pass
```javascript



### Notes

- This phase is essentially complete; adding tests to lock behavior

- Low risk since functionality already exists



---



## Phase 9.1 – Profiling (extra)



### Cursor Execution Prompt



```




## Task: Add Optional Profiling Support (PR 9.1)



### Goal

Add optional profiling dependencies and a profiling decorator that raises DependencyError if not installed.

### Scope

Files allowed to create:

- `cleanmydata/utils/profiling.py` (new)

Files allowed to modify:

- `pyproject.toml`
- `tests/test_smoke.py`



### Requirements

**Add to pyproject.toml:**

```toml

profiling = [

    "memory-profiler>=0.60.0",

    "line-profiler>=4.0.0",

]

```

**Create cleanmydata/utils/profiling.py:**

```python

"""Optional profiling utilities."""



from functools import wraps

from cleanmydata.exceptions import DependencyError



def profile_memory(func):

    """

    Decorator to profile memory usage.

    Raises DependencyError if memory_profiler not installed.

    """

    try:

        from memory_profiler import profile

    except ImportError as e:

        raise DependencyError(

            'Profiling support is not installed. Install with: pip install "cleanmydata[profiling]"'

        ) from e

    return profile(func)



def check_profiling_available() -> bool:

    """Check if profiling dependencies are available."""

    try:

        import memory_profiler  # noqa: F401

        import line_profiler  # noqa: F401

        return True

    except ImportError:

        return False

```



### Tests Required

1. `test_profiling_missing_dep` — using profile_memory without dep raises DependencyError
2. `test_check_profiling_available` — returns False when deps missing



### Constraints

- Do NOT add profiling to core dependencies
- Profiling is opt-in only
- DependencyError message must include install command



### Definition of Done

- profiling extra defined in pyproject.toml
- profiling.py exists with DependencyError handling
- Tests verify missing-dep behavior
```javascript



### Notes

- Dependency: None

- This is a minimal implementation; actual profiling integration is future work



---



## Phase 9.2 – Recipes (save/load YAML configs)



### Cursor Execution Prompt



```




## Task: Implement Config Recipes (PR 9.2)



### Goal

Add ability to save and load cleaning configurations as YAML "recipes".

### Scope

Files allowed to create:

- `cleanmydata/recipes.py` (new)

Files allowed to modify:

- `cleanmydata/cli.py`
- `tests/test_cli.py`



### Requirements

**Create cleanmydata/recipes.py:**

```python

"""Save and load cleaning recipes (YAML configurations)."""



from pathlib import Path

from cleanmydata.config import CleaningConfig



def save_recipe(config: CleaningConfig, path: Path) -> None:

    """

    Save a CleaningConfig as a YAML recipe file.



    Raises:

        DependencyError: If PyYAML not installed (should be with cli extra)

    """

    try:

        import yaml

    except ImportError as e:

        from cleanmydata.exceptions import DependencyError

        raise DependencyError(

            'YAML support requires CLI extra. Install with: pip install "cleanmydata[cli]"'

        ) from e



    data = {

        "outliers": config.outliers,

        "normalize_cols": config.normalize_cols,

        "clean_text": config.clean_text,

        "auto_outlier_detect": config.auto_outlier_detect,

    }



    with open(path, "w") as f:

        yaml.dump(data, f, default_flow_style=False)



def load_recipe(path: Path) -> CleaningConfig:

    """

    Load a CleaningConfig from a YAML recipe file.

    Validates at CLI boundary using CLIConfig if available.

    """

    try:

        import yaml

    except ImportError as e:

        from cleanmydata.exceptions import DependencyError

        raise DependencyError(

            'YAML support requires CLI extra. Install with: pip install "cleanmydata[cli]"'

        ) from e



    with open(path) as f:

        data = yaml.safe_load(f)



    return CleaningConfig(**data)

```

**Add CLI commands:**

- `cleanmydata recipe save <output_yaml> [options]` — save current options as recipe
- `cleanmydata recipe load <recipe_yaml> <input_file>` — apply recipe to file



### Tests Required

1. `test_save_recipe_creates_yaml` — save_recipe creates valid YAML
2. `test_load_recipe_returns_config` — load_recipe returns CleaningConfig
3. `test_recipe_roundtrip` — save then load preserves config



### Constraints

- Recipes are validated at CLI boundary
- Core CleaningConfig does not depend on YAML
- PyYAML is a CLI dependency, not core



### Definition of Done

- recipes.py exists with save/load functions
- CLI has recipe subcommand
- Roundtrip works correctly
- All tests pass
```javascript



### Notes

- Dependency: Phase 7.2 (config precedence uses YAML loading)

- PyYAML should already be in cli extra from Phase 7.2



---



## Phase 9.3 – Schema validation (pandera extra)



### Cursor Execution Prompt



```




## Task: Add Optional Schema Validation with Pandera (PR 9.3)



### Goal

Add optional schema validation support without polluting core dependencies.

### Scope

Files allowed to create:

- `cleanmydata/validation/schema.py` (new)

Files allowed to modify:

- `pyproject.toml`
- `cleanmydata/validation/__init__.py`
- `tests/test_validation.py` (new)



### Requirements

**Add to pyproject.toml:**

```toml

schema = [

    "pandera>=0.18.0",

]

```

**Create cleanmydata/validation/schema.py:**

```python

"""Optional schema validation using pandera."""



from cleanmydata.exceptions import DependencyError



def validate_schema(df, schema):

    """

    Validate DataFrame against a pandera schema.



    Args:

        df: DataFrame to validate

        schema: pandera DataFrameSchema



    Returns:

        ValidationResult with errors/warnings



    Raises:

        DependencyError: If pandera not installed

    """

    try:

        import pandera as pa

    except ImportError as e:

        raise DependencyError(

            'Schema validation requires pandera. Install with: pip install "cleanmydata[schema]"'

        ) from e



    from cleanmydata.models import ValidationResult



    result = ValidationResult()

    try:

        schema.validate(df, lazy=True)

    except pa.errors.SchemaErrors as err:

        for failure in err.failure_cases.itertuples():

            result.add_error(f"{failure.column}: {failure.check}")



    return result



def check_schema_available() -> bool:

    """Check if pandera is available."""

    try:

        import pandera  # noqa: F401

        return True

    except ImportError:

        return False

```



### Tests Required

1. `test_schema_validation_missing_dep` — raises DependencyError without pandera
2. `test_check_schema_available` — returns False when pandera missing



### Constraints

- Do NOT add pandera to core dependencies
- Schema validation is opt-in only
- DependencyError includes install command



### Definition of Done

- schema extra defined in pyproject.toml
- validation/schema.py exists
- DependencyError handling works
- Tests pass
```javascript



### Notes

- Dependency: Phase 4.1 (creates validation/ directory)

- Minimal implementation; full integration is future work



---



## Phase 10 – Documentation



### Cursor Execution Prompt



```




## Task: Create Core Documentation (PR 10)



### Goal

Create comprehensive documentation covering all required topics from the plan.

### Scope

Files allowed to create/modify:

- `README.md`
- `docs/install.md` (new)
- `docs/quickstart.md` (new)
- `docs/cli.md` (new)
- `docs/config.md` (new)
- `docs/formats.md` (new)
- `docs/architecture.md` (update existing)
- `docs/contributing.md` (new)



### Requirements

**README.md must include:**

- Project description
- Quick install command
- Basic usage example (library and CLI)
- Links to detailed docs

**docs/install.md:**

- Core install: `pip install cleanmydata`
- With CLI: `pip install "cleanmydata[cli]"`
- With Excel: `pip install "cleanmydata[excel]"`
- With Parquet: `pip install "cleanmydata[parquet]"`
- Development: `pip install -e ".[dev,test]"`

**docs/quickstart.md:**

- Library usage example
- CLI usage example
- Common options

**docs/cli.md:**

- All CLI commands and options
- Output modes (normal, quiet, silent)
- Exit codes (0, 1, 2, 3) with meanings
- Examples

**docs/config.md:**

- CleaningConfig options
- Config precedence (args > env > yaml > defaults)
- Environment variables
- YAML recipe format

**docs/formats.md:**

- CSV (always supported)
- Excel via `excel` extra
- Parquet via `parquet` extra
- .xls not supported (conversion hint)

**docs/contributing.md:**

- Development setup
- Running tests (`pytest`)
- Running linter (`ruff check`, `ruff format`)
- Running type checker (`mypy`)
- Running tox (`tox`)
- Release process



### Constraints

- Do NOT document unreleased features
- Do NOT include implementation details
- Keep examples minimal and working
- Use markdown consistently



### Definition of Done

- All documentation files created
- README.md updated with overview
- All examples are runnable
- No broken links
```javascript



### Notes

- Dependency: All previous phases should be complete

- Documentation reflects the implemented state, not planned features

- Can reference existing docs/architecture/ content



---



## Execution Order Summary




```
