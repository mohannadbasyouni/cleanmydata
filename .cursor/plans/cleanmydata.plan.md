# CleanMyData Refactor Plan

## Purpose

Transform CleanMyData into a production-ready cleaning **library + CLI** with:

- stable public API
- strict boundary separation (core vs CLI)
- reliable output modes + exit codes
- CI + tests + type checking
- multi-format I/O via optional extras
- **Excel optional in the library**, but **bundled by default in the future UI** via extras

---

## Current Status (Already Done ✅)

- Ruff configured in `pyproject.toml`
- Pre-commit hooks installed and enforced
- CI runs lint + tests and is green on `main`
- Pandas `SettingWithCopyWarning` eliminated + regression test added
- Smoke run confirmed working on `messy_data_10k.csv`

---

## Global Definition of Done (Applies to Every PR)

**Code Quality**

- `ruff format` passes
- `ruff check` passes
- no debug prints / no unresolved TODOs in merged PRs

**Testing**

- tests pass locally and in CI
- no skipped tests without documented reason
- PR includes tests for any new contract/behavior

**CI/CD**

- CI green on PRs + `main`

**Docs**

- CHANGELOG updated when user-facing behavior changes
- public API changes documented
- breaking changes include migration notes

**Stability**

- `main` always mergeable/shippable
- feature branches deleted after merge

---

## Non-Negotiable Architecture Rules (Authoritative)

1. **Core dependencies are minimal (library-first)**

Core deps are exactly:

- `pandas`
- `structlog`

2. **Excel is optional**

Excel support is an optional extra:

- `cleanmydata[excel] `installs `openpyxl`

3. **Core is UI-agnostic**

Core must not import:

- `rich`
- `typer`
- `pydantic`

4. **Config boundary**

- Core uses `CleaningConfig` (dataclass)
- CLI uses `CLIConfig` (Pydantic) **later** and converts into `CleaningConfig`

5. **Library-safe logging**

- use a named logger `"cleanmydata"`
- core never touches root logger
- core never auto-configures logging

6. **CLI wiring via factory**

- `AppContext.create()` wires console/logging/config once
- core functions do not auto-create context

---

## Python Support

- Minimum: **3.10**
- CI matrix later: **3.10 / 3.11 / 3.12**

---

# Phase 1 — Core Contracts + CLI Reliability (PR-sized)

**Goal:** lock CLI behavior + establish stable core primitives before any restructuring.

## PR 1.1 — Output modes contract + exit codes (authoritative)

**Output contract**

- **Normal:** info/progress on stdout; errors on stderr
- **Quiet:** no info/progress; errors on stderr
- **Silent:** no stdout; errors on stderr (still returns correct non-zero exit codes on failures)

**Exit codes**

- `0` success
- `1` general error
- `2` invalid input/config
- `3` I/O error

**Exit**

- automated tests confirm stdout/stderr behavior for normal/quiet/silent
- automated tests confirm exit codes for invalid input + I/O error + success

---

## PR 1.2 — Anchor modules (authoritative core surface)

Add/standardize:

- `constants.py`
- includes `.csv` always
- includes `.xlsx`/`.xlsm` as *recognized* formats, but requires excel extra at runtime
- **do NOT include `.parquet` yet**
- `exceptions.py`
- CleanMyDataError base
- `DependencyError` (missing optional deps)
- `InvalidInputError`
- `CleanIOError` (I/O failures wrapped consistently)
- `models.py`
- `CleaningResult`, `ValidationResult`
- success determined by **errors**, not warnings
- `config.py`
- `CleaningConfig` dataclass + `.validate()`

**Exit**

- core imports work
- CLI uses these modules directly (at least once each)

---

## PR 1.3 — I/O module + convenience API (Excel optional behavior enforced)

Create/standardize `cleanmydata/utils/io.py`:

### `read_data(path: Path) -> pd.DataFrame`

- `.csv` always supported with core install
- `.xlsx` / `.xlsm` supported only if `openpyxl` is installed
- if Excel requested and dependency missing:
- raise `DependencyError` with install hint:
    - `Excel support is not installed. Install with: pip install "cleanmydata[excel]"`

### `write_data(df: pd.DataFrame, path: Path) -> None`

- `.csv` always supported with core install
- `.xlsx` / `.xlsm` only if `openpyxl` installed
- same missing dependency behavior

### `clean_file(input_path, output_path, config=None) -> CleaningResult`

- reads input via `read_data`
- runs `clean_dataframe` (core)
- writes via `write_data`

**Exit**

- CLI cleans CSV end-to-end with core install
- attempting Excel without extra raises DependencyError with the exact hint
- tests cover:
- CSV read/write happy path
- Excel missing-dep error path (read + write)

---

## PR 1.4 — Logging: library-safe, simple, resettable

Create `cleanmydata/utils/logging.py`:

- `get_logger()` returns named logger `"cleanmydata"` only
- CLI-only `configure_logging(...)` configures handlers
- `reset_logging_for_tests()` exists and is used by tests

**Logging rules**

- console uses RichHandler (CLI-only)
- file uses stdlib Formatter
- structlog emits via stdlib logger
- no mixed formatting stacks

**Exit**

- no root logger config anywhere in core
- repeated calls do not duplicate handlers
- tests can reset logging cleanly

---

## PR 1.5 — AppContext factory + CLI wiring cleanup

Create `cleanmydata/context.py`:

- `AppContext.create(mode, log_to_file, verbose, config)` builds console/logger/config once
- silent overrides quiet
- CLI constructs one context and passes it through
- CLI maps exceptions to exit codes in exactly one place

**Exit**

- CLI has a single initialization point for console/logging/config
- exit-code mapping is centralized and fully testable

---

## Phase 1 Exit Criteria

- output modes + exit codes are locked by tests
- anchor modules exist and are used
- `clean_file` works end-to-end for CSV with core install
- Excel without extra fails with DependencyError + install hint
- logging is named + library-safe
- context wiring is centralized

---

# Phase 2 — Packaging + Extras Enforcement (Excel Optional Strategy)

**Goal:** ensure installs match the architecture rules and enforce extras behavior.

## PR 2.1 — Fix `pyproject.toml` to enforce minimal core + extras

**Core dependencies**

- keep: `pandas>=2.0.0`
- add: `structlog>=24.0.0`
- remove: `numpy` from core dependencies
- remove: `openpyxl` from core dependencies

**Optional dependencies**

- `cli`: `rich>=14.0.0`, `typer>=0.9.0`
- `excel`: `openpyxl>=3.1.0`
- `parquet`: `pyarrow>=10.0.0` (install-only for now)
- `test`: `pytest>=7.0.0`, `pytest-cov>=4.0.0`
- `dev`: `pre-commit`, `mypy`, `tox`

**Exit**

- `pip install .` works (core: CSV only)
- `pip install ".[excel]"` enables Excel read/write
- `pip install ".[cli]"` imports CLI
- `pip install ".[parquet]"` installs successfully (feature later)
- CI includes packaging job running these installs

---

## PR 2.2 — Add `all` extra explicitly (literal union only)

Define `all` as a literal union list of packages (no nested extras references).**Exit**

- `pip install ".[all]"` works reliably

---

## Phase 2 Exit Criteria

- packaging rules enforced by CI
- core install does not pull CLI or Excel deps
- Excel support works only when `excel` extra is installed

---

# Phase 3 — Tests That Matter (Coverage that buys confidence)

**Goal:** protect contracts and boundaries.**Coverage targets**

- overall: 70%+
- critical modules (config/exceptions/models/io/context/cli): 90%+

## PR 3.1 — Core unit tests

Add tests for:

- config validation
- exceptions/models correctness
- io CSV behavior
- io Excel missing-dep behavior
- logging reset behavior
- context creation + mode handling

**Exit**

- CI green
- coverage targets met for critical modules

---

## PR 3.2 — CLI contract tests (stdout/stderr/exit codes + extras behavior)

Use `typer.testing.CliRunner` and enforce:

- normal prints info/progress
- quiet prints no info/progress
- silent prints nothing on stdout
- errors always go to stderr
- exit codes match contract
- cleaning CSV works with core install
- cleaning Excel without `excel` extra fails with DependencyError message + correct exit code

**Exit**

- contracts cannot regress without CI failing

---

# Phase 4 — Restructure (Only after tests are strong)

**Goal:** reorganize modules without breaking behavior.

## PR 4.1 — Move to target structure (mechanical refactor)

Target structure:

- `cleanmydata/cleaning/` (core cleaning logic)
- `cleanmydata/utils/` (io/logging helpers)
- `cleanmydata/validation/`
- `cleanmydata/cli.py` (CLI boundary only)
- `cleanmydata/context.py`
- `cleanmydata/config.py`, `exceptions.py`, `models.py`, `constants.py`

**Exit**

- all Phase 3 tests pass unchanged

---

## PR 4.2 — Stable public API exports

In `cleanmydata/__init__.py` export only:

- `clean_dataframe`, `clean_file`
- `read_data`, `write_data`
- `CleaningConfig`
- result models
- exceptions
- `__version__`

**Exit**

- imports are stable
- version remains `0.1.0` until API stabilization is intentional

---

# Phase 5 — Types + Mypy (Relatively painless)

## PR 5.1 — Add type hints across core + utils

- prefer `Path`, `pd.DataFrame`, `CleaningConfig`
- avoid complex generics

## PR 5.2 — Add mypy in relaxed mode

- ignore missing imports
- warn return Any
- pass CI

**Exit**

- mypy green

---

# Phase 6 — Hardening (Confidence tooling)

## PR 6.1 — tox matrix

- 3.10 / 3.11 / 3.12

## PR 6.2 — Security scan (Bandit) non-blocking

- run Bandit in CI
- tune config to avoid noisy false positives
- do not fail builds except on real issues

## PR 6.3 — Expand tests to hit coverage targets

- focus coverage on contracts and boundaries
- add I/O error branch tests
- add logging guard tests

**Exit**

- tox green
- Bandit runs and reports
- coverage targets met

---

# Phase 7 — CLI Config Boundary (Pydantic)

**Goal:** strict input validation without polluting core.

## PR 7.1 — CLIConfig (Pydantic) + conversion

- CLI reads args/env/yaml
- validates in CLI only
- converts to `CleaningConfig`

## PR 7.2 — Config precedence contract

- args > env > yaml > defaults
- tests enforce precedence

## PR 7.3 — UX polish

- consistent error messages
- `raise typer.Exit(code=...)`
- mode handling consistent across all CLI paths

---

# Phase 8 — Parquet via Optional Extra

## PR 8.1 — Parquet read/write

- if `pyarrow` missing: raise `DependencyError` with install hint
- add `.parquet` to constants
- tests cover missing dependency path

## PR 8.2 — `.xls` explicitly rejected

- clear error + conversion hint
- tests

---

# Phase 9 — Optional Modules (No core bloat)

## PR 9.1 — Profiling (extra)

- optional profiling deps
- missing deps raise DependencyError

## PR 9.2 — Recipes

- save/load YAML configs validated at CLI boundary

## PR 9.3 — Schema validation (pandera extra)

- optional schema validation without polluting core

---

# Phase 10 — Documentation

Docs must include:

- install (core + extras: cli/excel/parquet)
- quickstart
- CLI usage + modes + exit codes
- config precedence
- formats (CSV always; Excel via `excel` extra; parquet via `parquet` extra)
- architecture boundaries
- contributing (tests, ruff, mypy, tox, release)

---

## Success Metrics

- CI always green on main
- core install does not pull CLI or Excel deps
- CLI output modes + exit codes locked by tests
- coverage: overall 70%+, critical modules 90%+
- tox passes 3.10–3.12
