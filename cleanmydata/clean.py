import re
import unicodedata

import numpy as np
import pandas as pd

try:
    from ddtrace import tracer
except ImportError:
    # Fallback for when ddtrace is not installed
    class NoOpTracer:
        """No-op tracer for when ddtrace is not available."""

        def trace(self, *args, **kwargs):
            """Return a no-op context manager."""
            from contextlib import nullcontext

            return nullcontext()

    tracer = NoOpTracer()

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

    from cleanmydata.utils import write_log

    start = time.time()
    error_message = None

    if df is None or df.empty:
        return df, {}

    # ---------- Initialize summary ----------
    summary = {
        "duplicates_removed": 0,
        "outliers_handled": 0,
        "missing_filled": 0,
        "columns_standardized": 0,
        "text_unconverted": 0,
    }

    try:
        with tracer.trace("cleaning.clean_data", service="cleanmydata") as span:
            span.set_tag("rows", len(df))
            span.set_tag("columns", len(df.columns))
            if dataset_name:
                span.set_tag("dataset_name", dataset_name)

            # ---------- 1. Remove duplicates ----------
            with tracer.trace("cleaning.remove_duplicates", service="cleanmydata") as dup_span:
                before = len(df)
                dup_span.set_tag("rows_before", before)
                df = remove_duplicates(df, verbose=verbose)
                after = len(df)
                summary["duplicates_removed"] = before - after
                dup_span.set_tag("rows_after", after)
                dup_span.set_tag("duplicates_removed", before - after)

            # ---------- 2. Normalize column names ----------
            if normalize_cols:
                with tracer.trace("cleaning.normalize_columns", service="cleanmydata"):
                    df = normalize_column_names(df, verbose=verbose)

            # ---------- 3. Clean text & categorical values ----------
            if clean_text:
                with tracer.trace("cleaning.clean_text", service="cleanmydata") as text_span:
                    before_text_cols = len(df.select_dtypes(include=["object", "string"]).columns)
                    text_span.set_tag("text_columns_before", before_text_cols)
                    df = clean_text_columns(
                        df,
                        lowercase=True,
                        verbose=verbose,
                        categorical_mapping=categorical_mapping,
                    )
                    summary["text_unconverted"] = before_text_cols  # tracked only

            # ---------- 4. Standardize formats ----------
            with tracer.trace("cleaning.standardize_formats", service="cleanmydata") as std_span:
                df = standardize_formats(df, verbose=verbose)
                converted_cols = [
                    c
                    for c in df.columns
                    if pd.api.types.is_numeric_dtype(df[c])
                    or pd.api.types.is_datetime64_any_dtype(df[c])
                ]
                summary["columns_standardized"] = len(converted_cols)
                std_span.set_tag("columns_standardized", len(converted_cols))

            # ---------- 5. Handle outliers ----------
            if outliers:
                with tracer.trace("cleaning.handle_outliers", service="cleanmydata") as out_span:
                    out_span.set_tag("method", outliers)
                    out_span.set_tag("auto_detect", auto_outlier_detect)
                    before_outlier_rows = len(df)
                    df = handle_outliers(
                        df, method=outliers, auto_detect=auto_outlier_detect, verbose=verbose
                    )
                    after_outlier_rows = len(df)
                    summary["outliers_handled"] = (
                        before_outlier_rows - after_outlier_rows if outliers == "remove" else 0
                    )
                    out_span.set_tag("rows_before", before_outlier_rows)
                    out_span.set_tag("rows_after", after_outlier_rows)

            # ---------- 6. Fill missing values ----------
            with tracer.trace("cleaning.fill_missing", service="cleanmydata") as miss_span:
                before_na = df.isna().sum().sum()
                miss_span.set_tag("missing_before", int(before_na))
                df = fill_missing_values(df, verbose=verbose)
                after_na = df.isna().sum().sum()
                summary["missing_filled"] = int(before_na - after_na)
                miss_span.set_tag("missing_filled", int(before_na - after_na))
                miss_span.set_tag("missing_after", int(after_na))

    except Exception as e:
        # Capture any unexpected error
        error_message = f"{type(e).__name__}: {e}"

    finally:
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
    """Removes duplicate rows from a DataFrame."""

    if df.empty:
        return (df, pd.DataFrame()) if return_report else df

    if subset:
        missing_cols = [c for c in subset if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Subset columns not found: {missing_cols}")

    # Optional normalization before duplicate detection
    if normalize_text:
        text_cols = df.select_dtypes(include="object").columns
        df.loc[:, text_cols] = df.loc[:, text_cols].apply(lambda col: col.str.strip().str.lower())

    dup_mask = df.duplicated(subset=subset, keep=keep)
    removed_rows = df.loc[dup_mask].copy()
    df_cleaned = df.loc[~dup_mask].copy()

    if return_report:
        return df_cleaned, removed_rows
    return df_cleaned


# ------------------- NORMALIZE COLUMN NAMES ------------------- #


def normalize_column_names(df, verbose=False):
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

    return df


# ------------------- TEXT CLEANING ------------------- #


def clean_text_columns(df, lowercase=True, verbose=False, categorical_mapping=None):
    def normalize_unicode(s):
        return unicodedata.normalize("NFKC", s) if isinstance(s, str) else s

    for col in df.select_dtypes(include=["object", "string"]):
        df.loc[:, col] = (
            df[col]
            .astype("string")
            .replace(["nan", "none", "null"], pd.NA)
            .str.strip()
            .replace(r"\s+", " ", regex=True)
            .map(normalize_unicode)
        )
        if lowercase:
            df.loc[:, col] = df[col].str.lower()

    if categorical_mapping:
        df = normalize_categorical_text(df, mapping=categorical_mapping, verbose=verbose)
    return df


# ------------------- CATEGORICAL NORMALIZATION ------------------- #


def normalize_categorical_text(df, mapping=None, verbose=False):
    """Normalize categorical values based on a provided mapping dictionary."""

    if mapping is None:
        return df

    for col, col_map in mapping.items():
        if col not in df.columns:
            continue

        # Preserve categorical dtype if present
        if pd.api.types.is_categorical_dtype(df[col]):
            df[col] = df[col].cat.add_categories(list(col_map.values())).replace(col_map)
        else:
            df[col] = df[col].replace(col_map)

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
                continue

        # ---------- DATETIME FALLBACK ----------
        temp = pd.to_datetime(series, errors="coerce", format="mixed")
        if temp.notna().mean() > 0.9:
            df[col] = temp
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

    return df


# ------------------- OUTLIER HANDLING ------------------- #


def handle_outliers(df, method="cap", auto_detect=True, verbose=False):
    """
    Handles outliers in numeric columns using IQR or Z-score detection.
    Can auto-switch based on column skewness.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outliers_removed = 0
    outliers_capped = {}

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

        # ---------- OUTLIER HANDLING ----------
        if method == "remove":
            df = df.loc[~mask].copy()
            outliers_removed += outlier_count

        elif method == "cap":
            df.loc[df[col] < lower, col] = lower
            df.loc[df[col] > upper, col] = upper
            outliers_capped[col] = outlier_count

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

    for col in df.columns:
        series = df[col]
        missing_count = series.isna().sum()
        if missing_count == 0:
            continue

        # Handle fully empty columns
        if series.dropna().empty:
            if np.issubdtype(series.dtype, np.number):
                fill_val = 0
            elif np.issubdtype(series.dtype, np.datetime64):
                fill_val = pd.Timestamp("1970-01-01")
            elif series.dtype == "bool":
                fill_val = False
            else:
                fill_val = "Unknown"
            df.loc[:, col] = series.fillna(fill_val)
            missing_filled += missing_count
            continue

        # ---------- NUMERIC ----------
        if np.issubdtype(series.dtype, np.number):
            skew_val = series.skew(skipna=True)

            if numeric_strategy == "median":
                fill_val = series.median()
            elif numeric_strategy == "mean":
                fill_val = series.mean()
            else:  # auto
                if abs(skew_val) > 0.75:
                    fill_val = series.median()
                else:
                    fill_val = series.mean()

            df.loc[:, col] = series.fillna(fill_val)

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
                        df.loc[:, col] = series.fillna(method="ffill")
                    elif dup_ratio > 0.3:
                        mode_val = series.mode()
                        fill_val = mode_val[0] if not mode_val.empty else series.median()
                        df.loc[:, col] = series.fillna(fill_val)
                    else:
                        fill_val = series.median()
                        df.loc[:, col] = series.fillna(fill_val)
                else:
                    fill_val = series.median()
                    df.loc[:, col] = series.fillna(fill_val)
            else:
                fill_val = series.median()
                df.loc[:, col] = series.fillna(fill_val)

        # ---------- BOOLEAN ----------
        elif series.dtype == "bool":
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else False
            df.loc[:, col] = series.fillna(fill_val)

        # ---------- CATEGORY ----------
        elif pd.api.types.is_categorical_dtype(series):
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else "Unknown"
            if fill_val not in series.cat.categories:
                series = series.cat.add_categories([fill_val])
            df.loc[:, col] = series.fillna(fill_val)

        # ---------- OBJECT / STRING ----------
        else:
            mode_val = series.mode()
            fill_val = mode_val[0] if not mode_val.empty else "Unknown"
            df.loc[:, col] = series.fillna(fill_val)

        missing_filled += missing_count

    return df
