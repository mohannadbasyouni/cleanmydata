import pandas as pd
import sys, threading, time
import itertools
import os
from datetime import datetime
from rich.console import Console

console = Console()

def print_section(title, level="sub", verbose=True):
    """Print formatted Rich section headers only if verbose=True."""
    if not verbose:
        return
    
    if level == "main":
        console.rule(f"[bold white]{title}[/bold white]", style="bright_green")
        console.print()
    elif level == "sub":
        console.rule(f"[bold cyan]{title}[/bold cyan]", style="dim cyan")

class Spinner:
    """Terminal spinner for indicating progress."""

    def __init__(self, message="Processing...", delay=0.1):
        self.spinner = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        self.delay = delay
        self.message = message
        self.stop_running = False
        self.thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        while not self.stop_running:
            sys.stdout.write(f"\r{self.message} {next(self.spinner)}")
            sys.stdout.flush()
            time.sleep(self.delay)
        sys.stdout.write(f"\r{self.message} \n")
        sys.stdout.flush()

    def start(self):
        self.stop_running = False
        self.thread.start()

    def stop(self):
        self.stop_running = True
        self.thread.join()

def load_data(filepath, verbose=True):
    """Load CSV or Excel dataset with feedback and error handling."""
    from src.utils import Spinner

    spinner = None
    message = f"Loading dataset: {os.path.basename(filepath)}"
    if not verbose:
        spinner = Spinner(message)
        spinner.start()
    else:
        print(f"\n{message} ...")

    try:
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        elif filepath.endswith((".xls", ".xlsx")):
            df = pd.read_excel(filepath)
        else:
            raise ValueError("Unsupported file format. Supported: .csv, .xls, .xlsx")

        if df.empty:
            print("\nLoaded file is empty.")
            return pd.DataFrame()

        if spinner:
            spinner.stop()

        print(f"Successfully loaded {df.shape[0]:,} rows × {df.shape[1]} columns.\n")
        return df

    except FileNotFoundError:
        print(f"\nError: File not found at {filepath}")
    except pd.errors.EmptyDataError:
        print("\nError: The file is empty or invalid.")
    except pd.errors.ParserError:
        print("\nError: Parsing error occurred while reading the file.")
    except Exception as e:
        print(f"\nUnexpected error while loading file: {e}")
    finally:
        if spinner:
            spinner.stop()

    return pd.DataFrame()

def write_log(summary, dataset_name, log_path="logs/cleaning_report.txt", status="completed", error=None):
    """
    Append structured run summary to log file.
    Automatically detects incomplete previous runs and logs failures if any.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Detect incomplete previous run
    previous_incomplete = False
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            last_lines = f.readlines()[-20:]
            has_completed = any("Completed" in line or "Failed" in line for line in last_lines)
            has_started = any("Cleaning Run" in line for line in last_lines)
            if has_started and not has_completed:
                previous_incomplete = True

    # Determine run number
    try:
        with open(log_path, "r", encoding="utf-8") as f:
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