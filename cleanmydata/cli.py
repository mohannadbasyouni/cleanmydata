"""CLI entrypoint for cleanmydata using Typer."""

import os
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from cleanmydata.clean import clean_data
from cleanmydata.exceptions import DataLoadError
from cleanmydata.utils.io import read_data

app = typer.Typer(
    name="cleanmydata",
    help="CleanMyData - A CLI data cleaning tool for automated cleaning of messy datasets",
)
console = Console()


@app.command()
def clean(
    path: str = typer.Argument(..., help="Path to dataset (.csv or .xls/.xlsx)"),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Output file name (default: original_cleaned.csv)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed cleaning logs"),
    log: bool = typer.Option(
        False, "--log", help="Save key cleaning details and summary to logs/cleaning_report.txt"
    ),
):
    """Clean a messy dataset."""
    try:
        df = read_data(Path(path))
    except (FileNotFoundError, DataLoadError) as e:
        console.print(f"[red]Error loading dataset: {e}[/red]")
        raise typer.Exit(code=1) from e

    if df.empty:
        console.print("[red]Failed to load dataset or file is empty.[/red]")
        raise typer.Exit(code=1)

    if verbose:
        console.rule("[bold]Original Data Preview[/bold]", style="white")

        preview = df.head(2)
        table = Table(show_header=True, header_style="bold white", box=box.MINIMAL)

        for col in preview.columns:
            table.add_column(col, overflow="fold")

        for _, row in preview.iterrows():
            table.add_row(*[str(v)[:80] for v in row.values])

        console.print(table)
        console.print(f"[dim]Rows:[/dim] {df.shape[0]:,}   [dim]Columns:[/dim] {df.shape[1]}\n")

    cleaned_df, summary = clean_data(
        df,
        verbose=verbose,
        log=log,
        dataset_name=os.path.basename(path),
    )

    if cleaned_df.empty:
        console.print("[red]No data cleaned — dataset is empty or invalid.[/red]")
        raise typer.Exit(code=1)

    filename = os.path.basename(path)
    name, ext = os.path.splitext(filename)
    output_path = output or os.path.join("data", f"{name}_cleaned{ext}")

    # Ensure output directory exists
    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True
    )

    cleaned_df.to_csv(output_path, index=False)

    console.print(f"\n[green]Cleaned data saved as '{output_path}'[/green]")


if __name__ == "__main__":
    app()
