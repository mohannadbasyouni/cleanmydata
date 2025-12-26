"""Utility functions for cleanmydata."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

try:
    from ddtrace import tracer as dd_tracer
except ImportError:
    dd_tracer = None

RUN_START_RE = re.compile(r"Cleaning Run #\d+ — Started")


# Deprecated: will remove in v0.2
def load_data(filepath, verbose=True):
    """
    Load CSV or Excel dataset.

    .. deprecated::
        This function is deprecated and will be removed in v0.2.
        Use :func:`cleanmydata.utils.io.read_data` instead.
    """
    from cleanmydata.utils.io import read_data

    return read_data(Path(filepath))


def write_log(
    summary, dataset_name, log_path="logs/cleaning_report.txt", status="completed", error=None
):
    """
    Append structured run summary to log file with Datadog trace correlation.
    Automatically detects incomplete previous runs and logs failures if any.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get Datadog trace context if available
    trace_id = None
    span_id = None
    if dd_tracer:
        current_span = dd_tracer.current_span()
        if current_span:
            trace_id = current_span.trace_id
            span_id = current_span.span_id

    # Detect incomplete previous run
    previous_incomplete = False
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            last_lines = f.readlines()[-20:]
            has_completed = any("Completed" in line or "Failed" in line for line in last_lines)
            has_started = any("Cleaning Run" in line for line in last_lines)
            if has_started and not has_completed:
                previous_incomplete = True

    # Determine run number (count only "Started" lines)
    try:
        with open(log_path, encoding="utf-8") as f:
            run_number = sum(1 for line in f if RUN_START_RE.search(line)) + 1
    except FileNotFoundError:
        run_number = 1

    # Write log entry
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"[{timestamp}] Cleaning Run #{run_number} — Started\n")
        if trace_id:
            f.write(f"Trace ID: {trace_id}   Span ID: {span_id}\n")
        f.write("-" * 80 + "\n")
        f.write(f"Dataset: {dataset_name}\n")
        f.write(f"Rows: {summary.get('rows', 0):,}   Columns: {summary.get('columns', 0)}\n")
        f.write("-" * 80 + "\n")

        if previous_incomplete:
            f.write("⚠ Previous run may not have completed cleanly.\n")
            f.write("-" * 80 + "\n")

        if summary:
            f.write(f"Duplicates removed: {summary.get('duplicates_removed', 0)}\n")
            f.write(f"Outliers handled: {summary.get('outliers_handled', 0)}\n")
            f.write(f"Missing values filled: {summary.get('missing_filled', 0)}\n")
            f.write(f"Columns standardized: {summary.get('columns_standardized', 0)}\n")
            f.write(f"Text columns unconverted: {summary.get('text_unconverted', 0)}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Duration: {summary.get('duration', 'N/A')}\n")

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if status == "failed":
            f.write(f"[{end_time}] ❌ Cleaning Run #{run_number} — Failed ({error})\n")
        else:
            f.write(f"[{end_time}] ✅ Cleaning Run #{run_number} — Completed\n")

        f.write("=" * 80 + "\n\n")


def get_trace_context():
    """
    Get current Datadog trace context for log correlation.

    Returns:
        dict: Dictionary containing dd.trace_id, dd.span_id, and dd.service
              Returns empty dict if no active trace.
    """
    context = {}
    if dd_tracer:
        current_span = dd_tracer.current_span()
        if current_span:
            context["dd.trace_id"] = str(current_span.trace_id)
            context["dd.span_id"] = str(current_span.span_id)
            context["dd.service"] = "cleanmydata"
    return context


def log_json(message, level="info", **extra_fields):
    """
    Write a JSON-formatted log entry with Datadog trace correlation.

    Args:
        message: Log message
        level: Log level (info, warning, error, etc.)
        **extra_fields: Additional fields to include in the log entry
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "message": message,
        "service": "cleanmydata",
    }

    # Add trace context if available
    trace_context = get_trace_context()
    log_entry.update(trace_context)

    # Add extra fields
    log_entry.update(extra_fields)

    # Write to stdout as JSON (for Datadog agent to collect)
    print(json.dumps(log_entry))
