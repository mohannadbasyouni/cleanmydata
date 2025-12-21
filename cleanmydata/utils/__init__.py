"""Utility functions for cleanmydata."""

import os
from datetime import datetime
from pathlib import Path


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
    Append structured run summary to log file.
    Automatically detects incomplete previous runs and logs failures if any.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Detect incomplete previous run
    previous_incomplete = False
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            last_lines = f.readlines()[-20:]
            has_completed = any("Completed" in line or "Failed" in line for line in last_lines)
            has_started = any("Cleaning Run" in line for line in last_lines)
            if has_started and not has_completed:
                previous_incomplete = True

    # Determine run number
    try:
        with open(log_path, encoding="utf-8") as f:
            run_number = sum(1 for line in f if "Cleaning Run #" in line) + 1
    except FileNotFoundError:
        run_number = 1

    # Write log entry
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"[{timestamp}] Cleaning Run #{run_number} — Started\n")
        f.write("-" * 80 + "\n")
        f.write(f"Dataset: {dataset_name}\n")
        f.write(f"Rows: {summary.get('rows', 0):,}   Columns: {summary.get('columns', 0)}\n")
        f.write("-" * 80 + "\n")

        if previous_incomplete:
            f.write("⚠ Previous run may not have completed cleanly.\n")
            f.write("-" * 80 + "\n")

        # Details (skip if failure before cleaning)
        if summary:
            f.write(f"Duplicates removed: {summary.get('duplicates_removed', 0)}\n")
            f.write(f"Outliers handled: {summary.get('outliers_handled', 0)}\n")
            f.write(f"Missing values filled: {summary.get('missing_filled', 0)}\n")
            f.write(f"Columns standardized: {summary.get('columns_standardized', 0)}\n")
            f.write(f"Text columns unconverted: {summary.get('text_unconverted', 0)}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Duration: {summary.get('duration', 'N/A')}\n")

        # Final line
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if status == "failed":
            f.write(f"[{end_time}] ❌ Cleaning Run #{run_number} — Failed ({error})\n")
        else:
            f.write(f"[{end_time}] ✅ Cleaning Run #{run_number} — Completed\n")

        f.write("=" * 80 + "\n\n")
