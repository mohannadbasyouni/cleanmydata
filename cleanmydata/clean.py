import re
import shutil
import unicodedata

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from cleanmydata.utils import print_section

console = Console()


def _vprint(message: str, color: str = None, verbose: bool = True):
    """Verbose-aware print helper using Rich console."""
    if verbose:
        console.print(message, style=color or "white")


# ------------------- CLEAN DATA MASTER ------------------- #


def clean_data(
    df,
    *,
    outliers="cap",
    normalize_cols=True,
    clean_text=True,
    categorical_mapping=None,
    auto_outlier_detect=True,
    verbose=False,
    log=False,
    dataset_name=None,
):
    """
    Master cleaning pipeline: sequentially applies cleaning operations to the input DataFrame.
    Logs both successful and failed runs if 'log=True'.
    """

    import time

    from cleanmydata.utils import Spinner, write_log

    start = time.time()
    error_message = None

    if df is None or df.empty:
        print("No data provided or DataFrame is empty.")
        return df, {}

    spinner = None
    message = "Cleaning data"
    if not verbose:
        spinner = Spinner(message)
        spinner.start()
    else:
        print_section("Cleaning Data", level="main")

    # ---------- Initialize summary ----------
    summary = {
        "duplicates_removed": 0,
        "outliers_handled": 0,
        "missing_filled": 0,
        "columns_standardized": 0,
        "text_unconverted": 0,
    }

    try:
        # ---------- 1. Remove duplicates ----------
        before = len(df)
        df = remove_duplicates(df, verbose=verbose)
        after = len(df)
        summary["duplicates_removed"] = before - after

        # ---------- 2. Normalize column names ----------
        if normalize_cols:
            df = normalize_column_names(df, verbose=verbose)

        # ---------- 3. Clean text & categorical values ----------
        if clean_text:
            before_text_cols = len(df.select_dtypes(include=["object", "string"]).columns)
            df = clean_text_columns(
                df,
                lowercase=True,
                verbose=verbose,
                categorical_mapping=categorical_mapping,
            )
            summary["text_unconverted"] = before_text_cols  # tracked only

        # ---------- 4. Standardize formats ----------
        df = standardize_formats(df, verbose=verbose)
        converted_cols = [
            c
            for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c])
        ]
        summary["columns_standardized"] = len(converted_cols)

        # ---------- 5. Handle outliers ----------
        if outliers:
            before_outlier_rows = len(df)
            df = handle_outliers(
                df, method=outliers, auto_detect=auto_outlier_detect, verbose=verbose
            )
            after_outlier_rows = len(df)
            summary["outliers_handled"] = (
                before_outlier_rows - after_outlier_rows if outliers == "remove" else 0
            )

        # ---------- 6. Fill missing values ----------
        before_na = df.isna().sum().sum()
        df = fill_missing_values(df, verbose=verbose)
        after_na = df.isna().sum().sum()
        summary["missing_filled"] = int(before_na - after_na)

    except Exception as e:
        # Capture any unexpected error
        error_message = f"{type(e).__name__}: {e}"
        print(f"\nAn error occurred during cleaning: {error_message}")

    finally:
        if spinner:
            spinner.stop()

        # ---------- Compute duration ----------
        elapsed = time.time() - start
        if elapsed < 60:
            duration = f"{elapsed:.2f}s"
        elif elapsed < 3600:
            mins, secs = divmod(elapsed, 60)
            duration = f"{int(mins)}m {secs:.0f}s"
        else:
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            duration = f"{int(hours)}h {int(mins)}m {secs:.0f}s"

        summary.update({"rows": df.shape[0], "columns": df.shape[1], "duration": duration})

        # ---------- Logging (success or failure) ----------
        if log:
            write_log(
                summary,
                dataset_name=dataset_name or "Unknown",
                status="failed" if error_message else "completed",
                error=error_message,
            )

    # ---------- CLI Summary ----------
    if not error_message:
        if verbose:
            print_section("Summary", level="main")
            console.print(f"• Rows: {df.shape[0]:,}   Columns: {df.shape[1]}")
            console.print(f"• Duration: {summary['duration']}\n")
            console.print(f"• {summary['duplicates_removed']:,} duplicates removed")
            console.print(f"• {summary['outliers_handled']:,} outliers handled")
            console.print(f"• {summary['missing_filled']:,} missing values filled")
            console.print(f"• {summary['columns_standardized']:,} columns standardized")
            console.print(f"• {summary['text_unconverted']:,} text columns unconverted")
            console.print("──────────────────────────────\n")
        else:
            print(
                f"Data cleaned successfully: "
                f"{summary['duplicates_removed']} duplicates, "
                f"{summary['outliers_handled']} outliers, "
                f"{summary['missing_filled']} missing filled "
                f"({summary['duration']})."
            )
    else:
        print(f"Cleaning failed: {error_message}")

    # ---------- If failure, re-raise for CLI awareness ----------
    if error_message:
        raise

    return df, summary


# ------------------- REMOVE DUPLICATES ------------------- #


def remove_duplicates(
    df,
    subset=None,
    keep="first",
    verbose=False,
    normalize_text=False,
    return_report=False,
):
    """Removes duplicate rows from a DataFrame with clear Rich-formatted output."""

    console = Console()

    if verbose:
        print_section("Duplicate Handling")

    if df.empty:
        _vprint("• No duplicates removed (empty dataset).", color="cyan", verbose=verbose)
        return (df, pd.DataFrame()) if return_report else df

    if subset:
        missing_cols = [c for c in subset if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Subset columns not found: {missing_cols}")

    # Optional normalization before duplicate detection
    if normalize_text:
        text_cols = df.select_dtypes(include="object").columns
        df[text_cols] = df[text_cols].apply(lambda col: col.str.strip().str.lower())

    initial_rows = len(df)
    dup_mask = df.duplicated(subset=subset, keep=keep)
    removed_rows = df[dup_mask]
    df_cleaned = df[~dup_mask]
    removed = len(removed_rows)
    pct = (removed / initial_rows * 100) if initial_rows else 0

    if verbose:
        if removed > 0:
            _vprint(
                f"• Duplicate rows removed: {removed} ({pct:.1f}%)", color="cyan", verbose=verbose
            )
            _vprint(
                f"  Example of removed rows (first {min(3, removed)} of {removed} shown):",
                color="dim",
                verbose=verbose,
            )

            # Build a Rich Table for removed row samples
            preview = removed_rows.head(3)
            table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)
            for col in preview.columns:
                table.add_column(col, overflow="fold")
            for _, row in preview.iterrows():
                table.add_row(*[str(v)[:80] for v in row.values])
            console.print(table)
        else:
            _vprint("• No duplicate rows exist.", color="cyan", verbose=verbose)

    if return_report:
        return df_cleaned, removed_rows
    return df_cleaned


# ------------------- NORMALIZE COLUMN NAMES ------------------- #


def normalize_column_names(df, verbose=False):
    old_cols = df.columns.tolist()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^0-9a-zA-Z_]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )

    seen, new_cols = {}, []
    for col in df.columns:
        if col not in seen:
            seen[col] = 0
            new_cols.append(col)
        else:
            seen[col] += 1
            new_col = f"{col}_{seen[col]}"
            while new_col in seen:
                seen[col] += 1
                new_col = f"{col}_{seen[col]}"
            seen[new_col] = 0
            new_cols.append(new_col)
    df.columns = new_cols

    if verbose:
        print_section("Column Name Normalization")
        renamed_pairs = [(o, n) for o, n in zip(old_cols, df.columns) if o != n]
        if renamed_pairs:
            _vprint(f"• {len(renamed_pairs)} column(s) renamed:", color="cyan", verbose=verbose)
            max_len = min(
                max(len(o) for o, _ in renamed_pairs) + 2,
                shutil.get_terminal_size((80, 20)).columns // 2,
            )
            for o, n in renamed_pairs:
                _vprint(f"  - {o:<{max_len}} → {n}", color="dim", verbose=verbose)
        else:
            _vprint("• No renaming needed.", color="cyan", verbose=verbose)
    return df


# ------------------- TEXT CLEANING ------------------- #


def clean_text_columns(df, lowercase=True, verbose=False, categorical_mapping=None):
    def normalize_unicode(s):
        return unicodedata.normalize("NFKC", s) if isinstance(s, str) else s

    for col in df.select_dtypes(include=["object", "string"]):
        df[col] = (
            df[col]
            .astype("string")
            .replace(["nan", "none", "null"], pd.NA)
            .str.strip()
            .replace(r"\s+", " ", regex=True)
            .map(normalize_unicode)
        )
        if lowercase:
            df[col] = df[col].str.lower()

    if verbose:
        print_section("Text Column Cleaning")
        text_cols = df.select_dtypes(include="object").columns
        _vprint(f"• {len(text_cols)} text column(s) cleaned:", color="cyan", verbose=verbose)
        _vprint(
            "  - Stripped whitespace, standardized spacing, normalized casing.",
            color="dim",
            verbose=verbose,
        )

    if categorical_mapping:
        df = normalize_categorical_text(df, mapping=categorical_mapping, verbose=verbose)
    return df


# ------------------- CATEGORICAL NORMALIZATION ------------------- #


def normalize_categorical_text(df, mapping=None, verbose=False):
    """Normalize categorical values based on a provided mapping dictionary."""

    if mapping is None:
        _vprint("• No categorical mappings provided.", color="cyan", verbose=verbose)
        return df

    if verbose:
        print_section("Categorical Normalization")

    for col, col_map in mapping.items():
        if col not in df.columns:
            _vprint(f"• Skipped '{col}' (column not found).", color="dim", verbose=verbose)
            continue

        # Preserve categorical dtype if present
        if pd.api.types.is_categorical_dtype(df[col]):
            df[col] = df[col].cat.add_categories(list(col_map.values())).replace(col_map)
        else:
            df[col] = df[col].replace(col_map)

        # Verbose-only details
        if verbose:
            unique_values = set(df[col].dropna().unique())
            mapped_keys = set(col_map.keys())
            unmapped = unique_values - mapped_keys

            _vprint(
                f"• Normalized '{col}' ({len(mapped_keys)} mapped)", color="cyan", verbose=verbose
            )
            if len(col_map) <= 5:
                for k, v in col_map.items():
                    _vprint(f"    - {k} → {v}", color="dim", verbose=verbose)
            if unmapped:
                preview = ", ".join(map(str, list(unmapped)[:3]))
                more = "" if len(unmapped) <= 3 else "..."
                _vprint(
                    f"    ⚠ Unmapped values remain: {len(unmapped)} unique ({preview}{more})",
                    color="yellow",
                    verbose=verbose,
                )

    return df


# ---------- COMPILED CONSTANTS ----------

CURRENCY_PATTERN = re.compile(
    r"(\b(?:USD|EUR|JPY|GBP|INR|AUD|CAD|CHF|CNY|HKD|SGD|MXN|NZD|SEK|NOK|DKK|KRW|RUB|BRL|ZAR|THB|TRY|ARS|EGP|PLN|BGN|HUF|COP|ILS|SAR|BHD|KWD|AED|DZD|NGN|PHP|PKR|BDT|VND|IDR|MYR|CLP|CZK)\b|"
    r"\$|€|¥|£|₹|A\$|C\$|NZ\$|S\$|kr|₩|₽|R\$|R|฿|₺|zł|лв|Ft|₪|﷼|د.إ|₦|₱|₨|₫|Rp)"
)

DATETIME_KEYWORDS = ["date", "time", "timestamp", "created", "modified", "updated", "dt"]
NUMERIC_KEYWORDS = [
    "price",
    "amount",
    "total",
    "cost",
    "score",
    "rate",
    "balance",
    "qty",
    "quantity",
]

# ---------- STANDARDIZE FORMATS ----------


def standardize_formats(df, verbose=False):
    converted_dt, converted_num = [], []
    total_converted = 0

    if verbose:
        print_section("Format Standardization")

    for col in df.columns:
        if df[col].dtype not in ["object", "string"]:
            continue

        series = df[col]
        col_lower = col.lower()

        # ---------- DATETIME DETECTION ----------
        if any(k in col_lower for k in DATETIME_KEYWORDS):
            temp = pd.to_datetime(series, errors="coerce", format="mixed")
            success_ratio = temp.notna().mean()
            if success_ratio > 0.8:
                df[col] = temp
                converted_dt.append(f"{col} → datetime ({success_ratio:.0%} parsed, keyword match)")
                total_converted += 1
                continue

        # ---------- DATETIME FALLBACK ----------
        temp = pd.to_datetime(series, errors="coerce", format="mixed")
        if temp.notna().mean() > 0.9:
            df[col] = temp
            converted_dt.append(f"{col} → datetime (fallback inference)")
            total_converted += 1
            continue

        # ---------- NUMERIC DETECTION ----------
        if (
            any(k in col_lower for k in NUMERIC_KEYWORDS)
            or series.astype(str).str.contains(r"\d", na=False).any()
        ):
            cleaned = series.astype(str)
            cleaned = (
                cleaned.str.replace(CURRENCY_PATTERN, "", regex=True)
                .str.replace(r"\(([\d.,]+)\)", r"-\1", regex=True)  # accounting negatives
                .str.replace(r"[,\s]", "", regex=True)
            )
            temp = pd.to_numeric(cleaned, errors="coerce")
            success_ratio = temp.notna().mean()
            if success_ratio > 0.8:
                df[col] = temp
                converted_num.append(f"{col} → numeric ({success_ratio:.0%} valid)")
                total_converted += 1

    # ---------- REPORT ----------
    if verbose:
        if converted_dt or converted_num:
            _vprint("• Datetime columns:", color="cyan", verbose=verbose)
            for item in converted_dt:
                _vprint(f"  - {item}", color="dim", verbose=verbose)

            _vprint("• Numeric columns:", color="cyan", verbose=verbose)
            for item in converted_num:
                _vprint(f"  - {item}", color="dim", verbose=verbose)

            # Summary
            total_text = len(df.select_dtypes(include=["object", "string"]).columns)
            _vprint("──────────────────────────────", color="dim", verbose=verbose)
            _vprint(
                f"• {total_converted} column(s) standardized successfully",
                color="green",
                verbose=verbose,
            )
            _vprint(
                f"• {total_text - total_converted} text columns unconverted",
                color="green",
                verbose=verbose,
            )
            _vprint("──────────────────────────────", color="dim", verbose=verbose)

        else:
            _vprint("• No columns need converting.", color="cyan", verbose=verbose)

    return df


# ------------------- OUTLIER HANDLING ------------------- #


def handle_outliers(df, method="cap", auto_detect=True, verbose=False):
    """
    Handles outliers in numeric columns using IQR or Z-score detection.
    Can auto-switch based on column skewness.
    Shows sample of removed rows only if method='remove' and count small enough.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outliers_removed = 0
    outliers_capped = {}
    removed_samples = pd.DataFrame()

    if verbose:
        print_section("Outlier Handling")

    for col in numeric_cols:
        series = df[col].dropna()
        if series.nunique() < 2:
            continue

        skew = series.skew()
        method_used = (
            "IQR" if (auto_detect and abs(skew) > 0.5) else "Z-score" if auto_detect else "IQR"
        )

        # ---------- OUTLIER BOUNDS ----------
        if method_used == "IQR":
            Q1, Q3 = series.quantile([0.25, 0.75])
            IQR = Q3 - Q1
            if IQR == 0:
                continue
            lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
        else:
            mean, std = series.mean(), series.std()
            if std == 0:
                continue
            lower, upper = mean - 3 * std, mean + 3 * std

        mask = (df[col] < lower) | (df[col] > upper)
        outlier_count = mask.sum()
        if outlier_count == 0:
            continue

        low_outliers = (df[col] < lower).sum()
        high_outliers = (df[col] > upper).sum()

        # ---------- OUTLIER HANDLING ----------
        if method == "remove":
            removed_rows = df.loc[mask, :]
            df = df.loc[~mask]
            outliers_removed += outlier_count

            # collect sample only if small
            if outlier_count <= 1000 and verbose and removed_samples.empty:
                removed_samples = removed_rows.head(3)
                removed_total = outlier_count

        elif method == "cap":
            df.loc[df[col] < lower, col] = lower
            df.loc[df[col] > upper, col] = upper
            outliers_capped[col] = outlier_count

        skew_desc = (
            "roughly symmetric"
            if abs(skew) < 0.3
            else "moderately skewed"
            if abs(skew) < 1
            else "highly skewed"
        )

        _vprint(
            f"• {col:<25} → {outlier_count} outliers handled "
            f"[{method_used}, skew={skew:.2f} ({skew_desc})]",
            color="cyan",
            verbose=verbose,
        )
        _vprint(f"  - low={low_outliers}, high={high_outliers}", color="dim", verbose=verbose)

    # ---------- REPORT ----------
    if verbose:
        if method == "remove" and outliers_removed > 0:
            _vprint(f"• Total outliers removed: {outliers_removed}", color="cyan", verbose=verbose)
        elif method == "cap" and outliers_capped:
            total_capped = sum(outliers_capped.values())
            _vprint(
                f"• Outliers capped across {len(outliers_capped)} column(s) "
                f"({total_capped} total).",
                color="cyan",
                verbose=verbose,
            )
        else:
            _vprint("• No significant outliers detected.", color="cyan", verbose=verbose)

        # ---------- SAMPLE PREVIEW ----------
        if method == "remove" and not removed_samples.empty:
            _vprint(
                f"  Example of removed outlier rows (first {len(removed_samples)} "
                f"of {removed_total} shown):",
                color="dim",
                verbose=verbose,
            )
            table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)
            for col in removed_samples.columns:
                table.add_column(col, overflow="fold")
            for _, row in removed_samples.iterrows():
                table.add_row(*[str(v)[:80] for v in row.values])
            console.print(table)

            _vprint("──────────────────────────────", color="dim", verbose=verbose)

    return df


# ------------------- FILL MISSING VALUES ------------------- #


def fill_missing_values(df, verbose=False, numeric_strategy="auto", datetime_strategy="median"):
    """
    Fill missing values intelligently by column dtype:
      • Numeric     → mean/median (auto-detects skewness if numeric_strategy='auto')
      • Datetime    → median/mode/ffill (auto-detects pattern if datetime_strategy='auto')
      • Boolean     → mode (or False)
      • Category    → mode (adds 'Unknown' if missing from categories)
      • Object/Text → mode (or 'Unknown')
    """

    missing_filled = 0

    if verbose:
        print_section("Missing Value Handling")

    for col in df.columns:
        series = df[col]
        missing_count = series.isna().sum()
        if missing_count == 0:
            continue

        # Handle fully empty columns
        if series.dropna().empty:
            if np.issubdtype(series.dtype, np.number):
                fill_val, method_used = 0, "constant 0 (empty column)"
            elif np.issubdtype(series.dtype, np.datetime64):
                fill_val, method_used = pd.Timestamp("1970-01-01"), "default date (empty column)"
            elif series.dtype == "bool":
                fill_val, method_used = False, "False (empty column)"
            else:
                fill_val, method_used = "Unknown", "'Unknown' (empty column)"
            df[col] = series.fillna(fill_val)
            missing_filled += missing_count
            _vprint(
                f"• {col:<25} → {missing_count} missing filled [{method_used}]",
                color="cyan",
                verbose=verbose,
            )
            continue

        # ---------- NUMERIC ----------
        if np.issubdtype(series.dtype, np.number):
            skew_val = series.skew(skipna=True)
            if abs(skew_val) < 0.5:
                skew_text = "roughly symmetric"
            elif abs(skew_val) < 1.5:
                skew_text = "moderately skewed"
            else:
                skew_text = "highly skewed"

            if numeric_strategy == "median":
                fill_val = series.median()
                method_used = "median (forced)"
            elif numeric_strategy == "mean":
                fill_val = series.mean()
                method_used = "mean (forced)"
            else:  # auto
                if abs(skew_val) > 0.75:
                    fill_val = series.median()
                    method_used = f"median (auto, skew={skew_val:.2f}, {skew_text})"
                else:
                    fill_val = series.mean()
                    method_used = f"mean (auto, skew={skew_val:.2f}, {skew_text})"

            df[col] = series.fillna(fill_val)
            _vprint(
                f"• {col:<25} → {missing_count} missing filled [{method_used}]",
                color="cyan",
                verbose=verbose,
            )

        # ---------- DATETIME ----------
        elif np.issubdtype(series.dtype, np.datetime64):
            if datetime_strategy == "auto":
                valid_series = series.dropna().sort_values()
                if len(valid_series) > 2:
                    time_diffs = valid_series.diff().dropna()
                    regularity = (
                        (time_diffs.std() / time_diffs.mean()).total_seconds()
                        if isinstance(time_diffs.mean(), pd.Timedelta)
                        else np.inf
                    )
                    dup_ratio = 1 - valid_series.nunique() / len(valid_series)

                    if regularity < 0.2:
                        df[col] = series.fillna(method="ffill")
                        method_used = "ffill (auto: regular intervals)"
                    elif dup_ratio > 0.3:
                        mode_val = series.mode()
                        fill_val = mode_val[0] if not mode_val.empty else series.median()
                        df[col] = series.fillna(fill_val)
                        method_used = "mode (auto: repetitive dates)"
                    else:
                        fill_val = series.median()
                        df[col] = series.fillna(fill_val)
                        method_used = "median (auto: irregular)"
                else:
                    fill_val = series.median()
                    df[col] = series.fillna(fill_val)
                    method_used = "median (fallback)"
            else:
                fill_val = series.median()
                df[col] = series.fillna(fill_val)
                method_used = "median (default)"

            _vprint(
                f"• {col:<25} → {missing_count} missing filled [{method_used}]",
                color="cyan",
                verbose=verbose,
            )

        # ---------- BOOLEAN ----------
        elif series.dtype == "bool":
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else False
            df[col] = series.fillna(fill_val)
            _vprint(
                f"• {col:<25} → {missing_count} missing filled [mode (bool)]",
                color="cyan",
                verbose=verbose,
            )

        # ---------- CATEGORY ----------
        elif pd.api.types.is_categorical_dtype(series):
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else "Unknown"
            if fill_val not in series.cat.categories:
                series = series.cat.add_categories([fill_val])
            df[col] = series.fillna(fill_val)
            _vprint(
                f"• {col:<25} → {missing_count} missing filled [mode (category)]",
                color="cyan",
                verbose=verbose,
            )

        # ---------- OBJECT / STRING ----------
        else:
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else "Unknown"
            df[col] = series.fillna(fill_val)
            _vprint(
                f"• {col:<25} → {missing_count} missing filled [mode (string)]",
                color="cyan",
                verbose=verbose,
            )

        missing_filled += missing_count

    if missing_filled > 0:
        _vprint(f"• Total missing values filled: {missing_filled}", color="cyan", verbose=verbose)
    else:
        _vprint("• No missing values detected.", color="cyan", verbose=verbose)

    return df
