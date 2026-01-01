"""Core I/O functions for reading and writing data files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import DataLoadError, DependencyError
from cleanmydata.models import CleaningResult


def read_data(path: Path | str) -> pd.DataFrame:
    """
    Read data from CSV, Excel (XLSX/XLSM), or Parquet file.

    Args:
        path: Path to the data file (.csv, .xlsx, .xlsm, or .parquet)

    Returns:
        DataFrame containing the loaded data

    Raises:
        DataLoadError: If the file cannot be read or format is unsupported
        FileNotFoundError: If the file does not exist
        DependencyError: If Excel/Parquet support is required but not installed
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    # Explicitly reject .xls (old Excel format)
    if suffix == ".xls":
        raise DataLoadError(
            "Unsupported file format: .xls (old Excel format). "
            "Please convert to .xlsx or .xlsm. Supported formats: .csv, .xlsx, .xlsm, .parquet"
        )

    try:
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".xlsx", ".xlsm"):
            try:
                import openpyxl  # noqa: F401
            except ImportError as e:
                raise DependencyError(
                    'Excel support is not installed. Install with: pip install "cleanmydata[excel]"'
                ) from e
            df = pd.read_excel(path)
        elif suffix == ".parquet":
            try:
                df = pd.read_parquet(path)
            except ImportError as e:
                raise DependencyError(
                    'Parquet support is not installed. Install with: pip install "cleanmydata[parquet]"'
                ) from e
        else:
            raise DataLoadError(
                f"Unsupported file format: {suffix}. Supported formats: .csv, .xlsx, .xlsm, .parquet"
            )

        return df

    except pd.errors.EmptyDataError as e:
        raise DataLoadError(f"The file is empty or invalid: {path}") from e
    except pd.errors.ParserError as e:
        raise DataLoadError(f"Parsing error occurred while reading the file: {path}") from e
    except DependencyError:
        raise
    except Exception as e:
        raise DataLoadError(f"Unexpected error while loading file {path}: {e}") from e


def write_data(df: pd.DataFrame, path: Path | str) -> None:
    """
    Write data to CSV, Excel (XLSX/XLSM), or Parquet file.

    Args:
        df: DataFrame to write
        path: Output file path (.csv, .xlsx, .xlsm, or .parquet)

    Raises:
        DataLoadError: If the file cannot be written or format is unsupported
        DependencyError: If Excel/Parquet support is required but not installed
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        df.to_csv(path, index=False)
        return

    # Explicitly reject .xls (old Excel format)
    if suffix == ".xls":
        raise DataLoadError(
            "Unsupported file format: .xls (old Excel format). "
            "Please convert to .xlsx or .xlsm. Supported formats: .csv, .xlsx, .xlsm, .parquet"
        )

    if suffix in (".xlsx", ".xlsm"):
        try:
            import openpyxl  # noqa: F401
        except ImportError as e:
            raise DependencyError(
                'Excel support is not installed. Install with: pip install "cleanmydata[excel]"'
            ) from e
        df.to_excel(path, index=False)
        return
    if suffix == ".parquet":
        try:
            df.to_parquet(path, index=False)
        except ImportError as e:
            raise DependencyError(
                'Parquet support is not installed. Install with: pip install "cleanmydata[parquet]"'
            ) from e
        return

    raise DataLoadError(
        f"Unsupported file format: {suffix}. Supported formats: .csv, .xlsx, .xlsm, .parquet"
    )


def clean_file(
    input_path: Path | str,
    output_path: Path | str,
    config: CleaningConfig | None = None,
) -> CleaningResult:
    """
    Convenience API to clean a file and write the result to disk.

    Args:
        input_path: Path to the input data file (.csv, .xlsx, .xlsm, or .parquet)
        output_path: Path to write the cleaned data (.csv, .xlsx, .xlsm, or .parquet)
        config: Optional CleaningConfig to customize cleaning behavior.
                If None, uses default CleaningConfig()

    Returns:
        CleaningResult containing summary statistics of the cleaning operation

    Raises:
        FileNotFoundError: If input_path does not exist
        DataLoadError: If the file cannot be read or written
        DependencyError: If Excel support is required but not installed
    """
    from cleanmydata.cleaning import clean_data

    # Use default config if not provided
    if config is None:
        config = CleaningConfig()

    # Read data
    df = read_data(input_path)

    # Clean data using the config
    cleaned_df, summary = clean_data(
        df,
        outliers=config.outliers,
        normalize_cols=config.normalize_cols,
        clean_text=config.clean_text,
        categorical_mapping=config.categorical_mapping,
        auto_outlier_detect=config.auto_outlier_detect,
        verbose=config.verbose,
    )

    # Write cleaned data
    write_data(cleaned_df, output_path)

    # Convert summary dict to CleaningResult
    result = CleaningResult(
        rows=summary.get("rows", 0),
        columns=summary.get("columns", 0),
        duplicates_removed=summary.get("duplicates_removed", 0),
        outliers_handled=summary.get("outliers_handled", 0),
        missing_filled=summary.get("missing_filled", 0),
        columns_standardized=summary.get("columns_standardized", 0),
        text_unconverted=summary.get("text_unconverted", 0),
        duration=summary.get("duration", ""),
    )

    return result
