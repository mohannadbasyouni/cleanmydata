# CleanMyData Baseline Verification Results

**Date:** 2025-12-21
**Environment:** Windows 10
**Python Version:** 3.13
**Test Environment:** `.venv_test` (clean virtual environment)

> **Note:** Baseline verification was performed on Python 3.13.
> Official project support targets Python ≥3.10; additional CI coverage for supported versions (3.10 / 3.11 / 3.12) will be added in later phases.

---

## Summary

All baseline verification tests passed successfully.
CleanMyData is functional in both **CLI** and **library** modes.

This baseline establishes a known-good reference point before Phase 1 refactoring.

---

## 1. Clean Test Environment Setup

**Commands:**

```bash
python -m venv .venv_test

# Activation (Windows)
# PowerShell:
.\.venv_test\Scripts\Activate.ps1

# cmd.exe:
.\.venv_test\Scripts\activate.bat

# Git Bash:
source .venv_test/Scripts/activate

pip install -U pip
pip install -e ".[cli]"
```

**Result:** ✅ PASS

* Virtual environment created successfully
* pip upgraded successfully
* Package installed in editable mode with CLI dependencies
* No install errors
* No dependency conflicts

**Key Dependencies Installed:**

* cleanmydata 0.1.0 (editable)
* pandas 2.3.3
* numpy 2.4.0
* openpyxl 3.1.5
* rich 14.2.0
* typer 0.20.1
* (plus transitive dependencies)

---

## 2. Library Import Sanity Check

**Command:**

```bash
python -c "import cleanmydata; print('import cleanmydata: OK'); from cleanmydata.clean import clean_data; print('import clean_data: OK')"
```

**Result:** ✅ PASS

* `import cleanmydata: OK`
* `import clean_data: OK`
* No `ImportError` or runtime exceptions

---

## 3. CLI Entrypoint Sanity Check

### 3a. Module Entrypoint

**Command:**

```bash
python -m cleanmydata --help
```

**Result:** ✅ PASS

* Exit code: `0`
* Help text displayed correctly
* Usage: `python -m cleanmydata [OPTIONS] PATH`
* Options listed: `--output`, `--verbose`, `--log`, `--help`
* No stack traces

### 3b. Console Script Entrypoint

**Command:**

```bash
cleanmydata --help
```

**Result:** ✅ PASS

* Exit code: `0`
* Help text displayed correctly
* Usage: `cleanmydata [OPTIONS] PATH`
* Both entrypoints behave identically

**Note:**
The CLI does **not** use a `clean` subcommand.
Invocation is directly `cleanmydata PATH` or `python -m cleanmydata PATH`.

---

## 4. End-to-End CLI Smoke Test (Valid Input)

**Command:**

```bash
python -m cleanmydata tests/fixtures/small.csv --output ./tmp/small_cleaned.csv
```

**Result:** ✅ PASS

* Exit code: `0`
* Output file created: `./tmp/small_cleaned.csv`
* File size: `138 bytes`
* File exists and is non-empty
* Command exits cleanly

**Input File:** `tests/fixtures/small.csv`

* Columns: `name`, `age`, `city`, `price`
* Rows: 5 (includes duplicates and missing values)

**Warnings Observed (non-fatal):**

* Multiple `SettingWithCopyWarning` warnings from pandas:

  * `cleanmydata/clean.py:202`
  * `cleanmydata/clean.py:211`
  * `cleanmydata/clean.py:406`

These warnings do not affect correctness but indicate internal copy/view handling that should be addressed during refactoring.

---

## 5. CLI Verbose + Logging Path Test

**Command:**

```bash
python -m cleanmydata tests/fixtures/small.csv --verbose --log
```

**Result:** ✅ PASS

* Exit code: `0`
* Verbose output displayed:

  * Original Data Preview table
  * Row/column counts shown: `Rows: 5   Columns: 4`
* Log file created: `logs/cleaning_report.txt`
* Log file size: `705 bytes`
* No crash during spinner or logging
* Output file saved to default path: `data/small_cleaned.csv`

**Sample Log Output:**

```text
[2025-12-21 04:34:30] Cleaning Run #1 — Started
Dataset: small.csv
Rows: 4   Columns: 4
Duplicates removed: 1
Outliers handled: 0
Missing values filled: 1
Columns standardized: 2
Text columns unconverted: 2
Duration: 0.01s
[2025-12-21 04:34:30] ✅ Cleaning Run #1 — Completed
```

---

## 6. Negative Test: Invalid Path

**Command:**

```bash
python -m cleanmydata does_not_exist.csv
echo $?
```

**Result:** ✅ PASS

* Exit code: `1`
* Error message: `Error loading dataset: File not found: does_not_exist.csv`
* Clear, user-friendly error
* No traceback

---

## 7. Negative Test: Unsupported Extension

**Note:**
The `.txt` file was created prior to this test to ensure the error reflects **unsupported format handling**, not missing file handling.

**Command:**

```bash
python -m cleanmydata tests/fixtures/small.txt
echo $?
```

**Result:** ✅ PASS

* Exit code: `1`
* Error message indicates unsupported format:

  ```text
  Unsupported file format: .txt. Supported formats: .csv, .xlsx, .xlsm
  ```

* No crash or traceback

---

## 8. Library-Level Execution Smoke Test

**Command:**

```python
import pandas as pd
from cleanmydata.clean import clean_data

df = pd.read_csv("tests/fixtures/small.csv")
out, summary = clean_data(df, verbose=False)

print("output shape:", out.shape)
print("summary keys:", sorted(summary.keys()))
```

**Result:** ✅ PASS

* No exceptions raised
* Output DataFrame returned successfully
* Output shape: `(4, 4)` (duplicate row removed)
* Summary dictionary populated with expected keys:

  * `rows`
  * `columns`
  * `duplicates_removed`
  * `outliers_handled`
  * `missing_filled`
  * `columns_standardized`
  * `text_unconverted`
  * `duration`

**Warnings Observed:**

* Same `SettingWithCopyWarning` warnings as in CLI execution

---

## Known Issues / Quirks

1. **Pandas `SettingWithCopyWarning`:**
   Multiple warnings indicate assignment on DataFrame views:

   * `cleanmydata/clean.py:202`
   * `cleanmydata/clean.py:211`
   * `cleanmydata/clean.py:406`
     These are non-fatal and should be addressed during Phase 1 cleanup without changing external behavior.

2. **Exit Codes (Current vs Planned):**
   Current behavior uses exit code `1` for most failure cases.
   Structured exit codes (`0` success, `1` general error, `2` invalid input/config, `3` I/O error) will be implemented in Phase 1.2.

3. **CLI Structure:**
   The CLI uses a direct invocation model (`cleanmydata PATH`), not subcommands.

---

## Files Created During Testing

* `.venv_test/` — Temporary test virtual environment
* `./tmp/small_cleaned.csv` — Output from end-to-end CLI test
* `data/small_cleaned.csv` — Output from verbose + log test
* `logs/cleaning_report.txt` — Log file generated via `--log`
* `tests/fixtures/small.txt` — Temporary file for unsupported extension test

---

## Conclusion

✅ **All baseline verification tests passed**

CleanMyData:

* Installs correctly in editable mode
* Imports cleanly as a library
* Exposes working CLI entrypoints
* Processes valid CSV files end-to-end
* Handles verbose output and logging correctly
* Provides clear, non-crashing error messages for invalid inputs
* Returns expected outputs and summaries at the library level

This baseline establishes a reliable reference point for Phase 1 refactoring and future regression testing.
