# CleanMyData Production-Ready Refactor Plan

## Purpose

Transform CleanMyData into a production-ready cleaning library + CLI with:

- stable public API
- strong boundary separation (core vs CLI)
- reliable output modes (normal/quiet/silent)
- CI + tests + type checking
- multi-format I/O via optional extras

---

## Global Definition of Done (applies to every phase)

**Code Quality**

- `ruff format` passes
- `ruff check` passes
- no debug prints / no unresolved TODOs in merged PRs

**Testing**

- all tests pass locally + in CI
- coverage meets phase target (see phases)
- no skipped tests without documented reason

**CI/CD**

- CI green on `main`
- lint + tests + (type check when added) all pass

**Docs**

- CHANGELOG updated per phase
- public API changes documented
- breaking changes include migration notes

**Stability**

- `main` always mergeable/shippable
- feature branches deleted after merge

---

## Non-Negotiable Architecture Rules

1) **Core dependency-minimal**
Core deps: `pandas`, `openpyxl`, `structlog` only.
CLI deps are extras.

2) **Core is UI-agnostic**
Core must not import `rich`, `typer`, `pydantic`.

3) **Boundary config**
Core uses `CleaningConfig` (dataclass).
CLI uses `CLIConfig` (Pydantic) and converts into `CleaningConfig`.

4) **Library-safe logging**
Use a named logger `"cleanmydata"`. Never touch root logger.
Core never auto-configures logging.

5) **CLI wiring via factory**
`AppContext.create()` wires console/logging/config.
Core functions do not auto-create context.

---

## Python Support

- Minimum: **3.10**
- CI/test matrix later: **3.10 / 3.11 / 3.12**

---

# Phase 1 — Foundation + Bug Fixes (PR-sized)

**Goal:** eliminate known bugs + establish anchor modules early.

### PR 1.1 — Fix known CLI bugs

- Fix: log message “jumping”
- Fix: quiet mode leaking output
- Fix: spinner cleanup on exceptions
- Improve: user-facing messages clarity
**Exit:** manual smoke: `clean` command behaves in normal/quiet/silent.

### PR 1.2 — Output modes contract + exit codes (implement)

- Implement modes:
- Normal: info+errors ok
- Quiet: suppress info/progress; keep errors on stderr
- Silent: no stdout/stderr
- Exit codes:
- 0 success
- 1 general error
- 2 invalid input/config
- 3 I/O error
**Exit:** running CLI returns correct output + exit codes.

### PR 1.3 — Add anchor modules (no big refactor yet)

Create:

- `constants.py` (IMPORTANT: **do NOT include `.parquet` yet**)
- `config.py` (`CleaningConfig` dataclass + `validate()`)
- `exceptions.py` (CleanMyDataError family)
- `models.py` (`CleaningResult`, `ValidationResult`; success based on **errors**, not warnings)
**Exit:** imports work and are used at least once by CLI/core.

### PR 1.4 — Add basic I/O module + convenience API

Create `utils/io.py`:

- `read_data()` supports `.csv`, `.xlsx`, `.xlsm`
- `write_data()` supports `.csv`, `.xlsx`, `.xlsm`
- define `clean_file(input_path, output_path, config=None)` calling core `clean_dataframe`
**Exit:** CLI can call `clean_file` end-to-end for csv/xlsx.

### PR 1.5 — Logging: simplify and make library-safe

Create `utils/logging.py`:

- named logger only (`cleanmydata`)
- CLI-only `configure_logging(...)`
- test helper `reset_logging_for_tests()`
- guard + `force=True` support
**Important:** don’t over-mix RichHandler + structlog formatting.
Pick one simple approach:
- console: RichHandler (human-readable)
- file: stdlib Formatter
- structlog configured to emit via stdlib logger
**Exit:** no root logger config; repeated calls safe; tests can reset.

### PR 1.6 — AppContext factory

Create `context.py`:

- `AppContext.create(...)` sets console/logger/config
- silent overrides quiet
- warnings capture only from CLI path (optional flag)
**Exit:** CLI builds context once and passes through.

**Phase 1 Exit Criteria**

- bugs fixed, anchor modules exist, clean_file works, modes behave, named logging works.

---

# Phase 2 — Quality Infrastructure (CI-first)

**Goal:** enforce linting + run tests + validate packaging/extras early.

### PR 2.1 — Ruff + pre-commit

- Add Ruff config to `pyproject.toml`
- Add `.pre-commit-config.yaml`
**Exit:** `pre-commit run --all-files` passes locally.

### PR 2.2 — CI: lint + tests

- Add `.github/workflows/ci.yml` with:
- lint job (ruff check + format --check)
- test job (pytest)
**Exit:** CI green on PR.

### PR 2.3 — Packaging/extras smoke job (early)

Add CI job that verifies:

- `pip install .` (core install)
- `pip install ".[cli]"` imports CLI module
- `pip install ".[parquet]"` just verifies install succeeds (feature later)
**Exit:** packaging job green.

**Phase 2 Exit Criteria**

- CI green, lint enforced, extras validated.

---

# Phase 3 — Basic Tests (30–40% coverage)

**Goal:** protect boundaries and output modes before restructure.

### PR 3.1 — Test skeleton + key unit tests

Add `tests/` with:

- config validation tests
- exceptions/models tests
- io read/write happy path tests
- context creation tests
**Exit:** tests pass in CI.

### PR 3.2 — CLI output modes tests (robust)

- Use Typer/Cliqk runner with stderr separated:
- `CliRunner(mix_stderr=False)` if available
- Silent mode asserts:
- stdout == ""
- stderr == ""
- Avoid brittle Rich string checks (assert empty/non-empty only)
**Exit:** mode behavior locked by tests.

**Phase 3 Exit Criteria**

- coverage 30–40%, output modes reliably tested.

---

# Phase 4 — Restructure (after tests)

**Goal:** reorganize modules without breaking behavior.

### PR 4.1 — Move to target structure (mechanical refactor)

Target:
cleanmydata/
cleaning/
utils/
validation/
profiling/
...
Keep core UI-agnostic.

### PR 4.2 — Stable public API exports

- `cleanmydata/__init__.py` exports:
- clean_dataframe, clean_file
- read_data, write_data
- CleaningConfig
- result models
- custom exceptions
- Version: start `0.1.0`
**Exit:** Phase 3 tests still pass unchanged.

**Phase 4 Exit Criteria**

- structure clean, API stable, tests passing.

---

# Phase 5 — Types + Mypy (relaxed)

**Goal:** add type hints without slowing dev.

### PR 5.1 — Add type hints in core + utils

- prefer `Path`, `pd.DataFrame`, `CleaningConfig`
- avoid `Any` unless unavoidable

### PR 5.2 — Add mypy relaxed

- ignore missing imports
- warn return Any
**Exit:** mypy passes.

**Phase 5 Exit Criteria**

- mypy green (relaxed), types improve signatures.

---

# Phase 6 — Hardening (80%+ coverage + tox + security)

**Goal:** production confidence.

### PR 6.1 — Expand tests to 80%+

- hypothesis property tests where meaningful
- logging tests (guard/force/reset)
- output modes exhaustive
- io error branches (permissions, missing files)

### PR 6.2 — tox matrix

- 3.10 / 3.11 / 3.12

### PR 6.3 — bandit (reasonable config)

- don’t fail build on noisy pandas patterns unless real issues

### PR 6.4 — selective strict mypy

- strict in utils/context/cli/config/models/exceptions
- lighter in cleaning modules initially

**Phase 6 Exit Criteria**

- 80%+ coverage, tox green, security scan added, selective strict typing green.

---

# Phase 7 — CLI & Config (Pydantic boundary)

**Goal:** modern CLI UX with strict boundary.

### PR 7.1 — CLIConfig (Pydantic) + conversion

- CLI reads args/env/yaml
- validates via Pydantic
- converts into `CleaningConfig`

### PR 7.2 — Config precedence

args > env > yaml > defaults

### PR 7.3 — Typer UX polish

- use `raise typer.Exit(code=...)`
- explicitly honor quiet/silent everywhere

**Phase 7 Exit Criteria**

- config boundary enforced, CLI consistent.

---

# Phase 8 — Multi-format I/O (Parquet)

**Goal:** add `.parquet` via optional extra safely.

### PR 8.1 — Parquet read/write

- if pyarrow missing: raise `DependencyError` with install hint
- update constants: add `.parquet` to SUPPORTED_FORMATS
- tests cover missing pyarrow path

### PR 8.2 — `.xls` explicitly rejected

- helpful error message + how to convert
- tests for `.xls` rejection

**Phase 8 Exit Criteria**

- CSV/XLSX/XLSM/Parquet supported; `.xls` rejected cleanly.

---

# Phase 9 — Optional Modules (profiling/validation/recipes)

**Goal:** features without dependency bloat.

### PR 9.1 — Profiling extra

- optional `profiling` extra
- missing deps => `DependencyError`

### PR 9.2 — Recipes

- save/load YAML configs validated at CLI boundary

### PR 9.3 — Schema validation (pandera extra)

- optional validate/infer

**Phase 9 Exit Criteria**

- optional features work without polluting core deps.

---

# Phase 10 — Documentation

**Goal:** usable docs + contributor guide.

Docs:

- installation
- quickstart
- cli usage + output modes
- configuration + precedence
- formats
- architecture (dependency split / logging / config boundary)
- dev docs (testing, DoD)

**Phase 10 Exit Criteria**

- docs complete, API documented, CHANGELOG maintained.

---

## Packaging Rules (extras)

- Core deps only in `[project.dependencies]`
- CLI deps only in `[project.optional-dependencies].cli`
- `all` is literal union list (no nested extras references)

---

## Success Metrics

- CI always green on main
- coverage 80%+
- tox passes 3.10–3.12
- library install does not pull CLI deps
- silent mode produces zero stdout/stderr
- stable public API + documented changes
