import re
import time
import unicodedata

import numpy as np
import pandas as pd

from cleanmydata.constants import OUTLIER_METHODS
from cleanmydata.exceptions import InvalidInputError
from cleanmydata.metrics import MetricsClient, default_metric_tags, get_metrics_client
from cleanmydata.utils.logging import get_logger

try:
    from ddtrace import tracer
except ImportError:
    # Fallback for when ddtrace is not installed
    class _NoOpSpan:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, D401
            return False

        def set_tag(self, *args, **kwargs):  # noqa: ARG002
            return None

    class NoOpTracer:
        """No-op tracer for when ddtrace is not available."""

        def trace(self, *args, **kwargs):
            """Return a no-op context manager."""

            return _NoOpSpan()

    tracer = NoOpTracer()


logger = get_logger(__name__)


def _safe_emit(
    emit_fn,
    name: str,
    value: float,
    tags: list[str],
) -> None:
    try:
        emit_fn(name, value, tags)
    except Exception as exc:  # pragma: no cover - best-effort
        logger.debug("metrics_emit_failed", metric=name, error=str(exc))


def _determine_dataset_kind(dataset_name: str | None) -> str | None:
    """Return a bounded dataset kind based on file extension."""
    if not dataset_name:
        return None

    lowered = str(dataset_name).lower()
    if lowered.endswith((".xlsx", ".xlsm")):
        return "excel"
    if lowered.endswith(".csv"):
        return "csv"
    return "unknown"


def _build_metric_tags(
    dataset_name: str | None,
    outliers_method: str | None,
    excel_used: bool | None,
    dataset_kind: str | None = None,
) -> list[str]:
    kind = dataset_kind or _determine_dataset_kind(dataset_name)
    tags = default_metric_tags() + ["runtime:cloudrun"]
    if kind:
        tags.append(f"dataset_kind:{kind}")
    if outliers_method:
        tags.append(f"outliers_method:{outliers_method}")
    if excel_used is not None:
        tags.append(f"excel_used:{str(excel_used).lower()}")
    return tags


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
    metrics_client: MetricsClient | None = None,
    excel_used: bool | None = None,
):
    """
    Master cleaning pipeline: sequentially applies cleaning operations to the input DataFrame.
    Structured logs are always emitted via structlog; the 'log' flag is kept for
    compatibility and no longer writes log files.
    """

    metrics = metrics_client or get_metrics_client()
    _ = log  # backward compatibility (no-op)

    dataset_kind = _determine_dataset_kind(dataset_name)
    derived_excel_used = (
        excel_used
        if excel_used is not None
        else (dataset_kind == "excel" if dataset_name else None)
    )
    base_tags = _build_metric_tags(dataset_name, outliers, derived_excel_used, dataset_kind)
    _safe_emit(metrics.count, "cleanmydata.requests_total", 1, base_tags)

    start_wall = time.time()
    start_perf = time.perf_counter()
    error_message = None

    def _log_step(
        step: str, *, rows_before=None, rows_after=None, duration_ms=None, **fields
    ) -> None:
        payload = {"step": step, "duration_ms": duration_ms, **fields}
        if rows_before is not None:
            payload["rows_before"] = rows_before
        if rows_after is not None:
            payload["rows_after"] = rows_after
        logger.info("clean_step_completed", **payload)

    # ---------- Initialize summary ----------
    summary = {
        "duplicates_removed": 0,
        "outliers_handled": 0,
        "missing_filled": 0,
        "columns_standardized": 0,
        "text_unconverted": 0,
    }

    logger.info(
        "clean_request_started",
        dataset_name=dataset_name,
        rows=0 if df is None else len(df),
        columns=0 if df is None else len(df.columns),
        outliers_method=outliers,
        normalize_cols=normalize_cols,
        clean_text=clean_text,
        auto_outlier_detect=auto_outlier_detect,
        dataset_kind=dataset_kind,
        excel_used=derived_excel_used,
    )

    if outliers not in OUTLIER_METHODS:
        raise InvalidInputError(
            f"Invalid outliers value: {outliers!r} (expected one of {OUTLIER_METHODS})"
        )

    if df is None or df.empty:
        elapsed_ms = int((time.perf_counter() - start_perf) * 1000)
        status_tags = base_tags + ["status:failure"]
        _safe_emit(metrics.count, "cleanmydata.requests_failed_total", 1, status_tags)
        _safe_emit(metrics.histogram, "cleanmydata.duration_ms", elapsed_ms, status_tags)
        logger.error(
            "clean_request_completed",
            status="failure",
            rows=0,
            columns=0,
            duration_ms=elapsed_ms,
            dataset_name=dataset_name,
            reason="empty_dataframe",
        )
        raise InvalidInputError("Input dataframe is empty.")

    try:
        with tracer.trace("cleaning.clean_data", service="cleanmydata") as span:
            span.set_tag("rows", len(df))
            span.set_tag("columns", len(df.columns))
            if dataset_kind:
                span.set_tag("dataset_kind", dataset_kind)

            # ---------- 1. Remove duplicates ----------
            with tracer.trace("cleaning.remove_duplicates", service="cleanmydata") as dup_span:
                before = len(df)
                dup_span.set_tag("rows_before", before)
                step_start = time.perf_counter()
                df = remove_duplicates(df, verbose=verbose)
                after = len(df)
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                summary["duplicates_removed"] = before - after
                dup_span.set_tag("rows_after", after)
                dup_span.set_tag("duplicates_removed", before - after)
                _log_step(
                    "remove_duplicates",
                    rows_before=before,
                    rows_after=after,
                    duration_ms=duration_ms,
                    duplicates_removed=before - after,
                )

            # ---------- 2. Normalize column names ----------
            if normalize_cols:
                with tracer.trace("cleaning.normalize_columns", service="cleanmydata"):
                    step_start = time.perf_counter()
                    columns_before = len(df.columns)
                    df = normalize_column_names(df, verbose=verbose)
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    _log_step(
                        "normalize_columns",
                        rows_before=len(df),
                        rows_after=len(df),
                        duration_ms=duration_ms,
                        columns_before=columns_before,
                        columns_after=len(df.columns),
                    )
            else:
                _log_step(
                    "normalize_columns",
                    rows_before=len(df),
                    rows_after=len(df),
                    duration_ms=0,
                    status="skipped",
                )

            # ---------- 3. Clean text & categorical values ----------
            if clean_text:
                with tracer.trace("cleaning.clean_text", service="cleanmydata") as text_span:
                    before_text_cols = len(df.select_dtypes(include=["object", "string"]).columns)
                    text_span.set_tag("text_columns_before", before_text_cols)
                    step_start = time.perf_counter()
                    df = clean_text_columns(
                        df,
                        lowercase=True,
                        verbose=verbose,
                        categorical_mapping=categorical_mapping,
                    )
                    summary["text_unconverted"] = before_text_cols  # tracked only
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    _log_step(
                        "clean_text",
                        rows_before=len(df),
                        rows_after=len(df),
                        duration_ms=duration_ms,
                        text_columns_before=before_text_cols,
                    )
            else:
                _log_step(
                    "clean_text",
                    rows_before=len(df),
                    rows_after=len(df),
                    duration_ms=0,
                    status="skipped",
                )

            # ---------- 4. Standardize formats ----------
            with tracer.trace("cleaning.standardize_formats", service="cleanmydata") as std_span:
                step_start = time.perf_counter()
                df = standardize_formats(df, verbose=verbose)
                converted_cols = [
                    c
                    for c in df.columns
                    if pd.api.types.is_numeric_dtype(df[c])
                    or pd.api.types.is_datetime64_any_dtype(df[c])
                ]
                summary["columns_standardized"] = len(converted_cols)
                std_span.set_tag("columns_standardized", len(converted_cols))
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                _log_step(
                    "standardize_formats",
                    rows_before=len(df),
                    rows_after=len(df),
                    duration_ms=duration_ms,
                    columns_standardized=len(converted_cols),
                )

            # ---------- 5. Handle outliers ----------
            if outliers:
                with tracer.trace("cleaning.handle_outliers", service="cleanmydata") as out_span:
                    out_span.set_tag("method", outliers)
                    out_span.set_tag("auto_detect", auto_outlier_detect)
                    before_outlier_rows = len(df)
                    step_start = time.perf_counter()
                    df = handle_outliers(
                        df, method=outliers, auto_detect=auto_outlier_detect, verbose=verbose
                    )
                    after_outlier_rows = len(df)
                    summary["outliers_handled"] = (
                        before_outlier_rows - after_outlier_rows if outliers == "remove" else 0
                    )
                    out_span.set_tag("rows_before", before_outlier_rows)
                    out_span.set_tag("rows_after", after_outlier_rows)
                    duration_ms = int((time.perf_counter() - step_start) * 1000)
                    _log_step(
                        "handle_outliers",
                        rows_before=before_outlier_rows,
                        rows_after=after_outlier_rows,
                        duration_ms=duration_ms,
                        outliers_handled=summary["outliers_handled"],
                        method=outliers,
                    )
            else:
                _log_step(
                    "handle_outliers",
                    rows_before=len(df),
                    rows_after=len(df),
                    duration_ms=0,
                    status="skipped",
                    method=outliers,
                )

            # ---------- 6. Fill missing values ----------
            with tracer.trace("cleaning.fill_missing", service="cleanmydata") as miss_span:
                before_na = df.isna().sum().sum()
                miss_span.set_tag("missing_before", int(before_na))
                step_start = time.perf_counter()
                df = fill_missing_values(df, verbose=verbose)
                after_na = df.isna().sum().sum()
                summary["missing_filled"] = int(before_na - after_na)
                miss_span.set_tag("missing_filled", int(before_na - after_na))
                miss_span.set_tag("missing_after", int(after_na))
                duration_ms = int((time.perf_counter() - step_start) * 1000)
                _log_step(
                    "fill_missing",
                    rows_before=len(df),
                    rows_after=len(df),
                    duration_ms=duration_ms,
                    missing_before=int(before_na),
                    missing_after=int(after_na),
                    missing_filled=int(before_na - after_na),
                )

    except Exception as e:
        # Capture any unexpected error and preserve traceback
        error_message = f"{type(e).__name__}: {e}"
        logger.error(
            "clean_request_failed",
            error_type=type(e).__name__,
            error_message=str(e),
            dataset_name=dataset_name,
            exc_info=True,
        )
        raise

    finally:
        # ---------- Compute duration ----------
        elapsed = time.time() - start_wall
        elapsed_ms = int(elapsed * 1000)
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

        status = "failure" if error_message else "success"
        status_tags = base_tags + [f"status:{status}"]
        _safe_emit(metrics.histogram, "cleanmydata.duration_ms", elapsed_ms, status_tags)
        _safe_emit(
            metrics.gauge,
            "cleanmydata.rows_processed",
            summary.get("rows", 0),
            base_tags,
        )
        _safe_emit(
            metrics.gauge,
            "cleanmydata.columns_processed",
            summary.get("columns", 0),
            base_tags,
        )
        _safe_emit(
            metrics.gauge,
            "cleanmydata.duplicates_removed",
            summary.get("duplicates_removed", 0),
            base_tags,
        )
        _safe_emit(
            metrics.gauge,
            "cleanmydata.missing_filled",
            summary.get("missing_filled", 0),
            base_tags,
        )
        _safe_emit(
            metrics.gauge,
            "cleanmydata.outliers_handled",
            summary.get("outliers_handled", 0),
            base_tags,
        )
        if error_message:
            _safe_emit(metrics.count, "cleanmydata.requests_failed_total", 1, status_tags)
        else:
            _safe_emit(metrics.count, "cleanmydata.requests_succeeded_total", 1, status_tags)

        log_fn = logger.error if error_message else logger.info
        log_fn(
            "clean_request_completed",
            status=status,
            rows=summary.get("rows", 0),
            columns=summary.get("columns", 0),
            duration_ms=elapsed_ms,
            dataset_name=dataset_name,
        )

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
    cols = pd.Index(df.columns)
    col_strings = pd.Series(cols, dtype="object").map(lambda c: "" if c is None else str(c))
    normalized = (
        col_strings.str.strip()
        .str.lower()
        .str.replace(r"[^0-9a-zA-Z_]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    df.columns = pd.Index(normalized.tolist())

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
