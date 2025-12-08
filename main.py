import argparse
import os
from rich.console import Console
from rich.table import Table
from rich import box
from src.clean import clean_data
from src.utils import load_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CleanMyData - Clean a messy dataset")
    parser.add_argument("path", help="Path to dataset (.csv or .xls/.xlsx)")
    parser.add_argument("--output", default=None, help="Output file name (default: original_cleaned.csv)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed cleaning logs")
    parser.add_argument("--log", action="store_true", help="Save key cleaning details and summary to logs/cleaning_report.txt")
    args = parser.parse_args()

    df = load_data(args.path, verbose=args.verbose)

    if df.empty:
        print("Failed to load dataset or file is empty.")
        exit()

    if args.verbose:
        console = Console()    
        console.rule("[bold]Original Data Preview[/bold]", style="white")

        preview = df.head(2)
        table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)

        for col in preview.columns:
            table.add_column(col, overflow="fold")

        for _, row in preview.iterrows():
            table.add_row(*[str(v)[:80] for v in row.values])  # limit long text for readability

        console.print(table)
        console.print(f"[dim]Rows:[/dim] {df.shape[0]:,}   [dim]Columns:[/dim] {df.shape[1]}\n")

    cleaned_df, summary = clean_data(
    df,
    verbose=args.verbose,
    log=args.log,
    dataset_name=os.path.basename(args.path)
    )

    if cleaned_df.empty:
        print("\nNo data cleaned — dataset is empty or invalid.")
        exit()

    filename = os.path.basename(args.path)
    name, ext = os.path.splitext(filename)
    output_path = args.output or os.path.join("data", f"{name}_cleaned{ext}")
    cleaned_df.to_csv(output_path, index=False)

    print(f"\nCleaned data saved as '{output_path}'")

    if args.log:
        from src.utils import write_log
        write_log(args.path, cleaned_df, summary, verbose=args.verbose)
