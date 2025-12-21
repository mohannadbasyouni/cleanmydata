"""Core I/O functions for reading and writing data files."""

from pathlib import Path

import pandas as pd

from cleanmydata.exceptions import DataLoadError, DependencyError


def read_data(path: Path) -> pd.DataFrame:
    """
    Read data from CSV or Excel file (XLSX/XLSM only).

    Args:
        path: Path to the data file (.csv, .xlsx, or .xlsm)

    Returns:
        DataFrame containing the loaded data

    Raises:
        DataLoadError: If the file cannot be read or format is unsupported
        FileNotFoundError: If the file does not exist
        DependencyError: If Excel support is required but not installed
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    # Explicitly reject .xls (old Excel format)
    if suffix == ".xls":
        raise DataLoadError(
            "Unsupported file format: .xls (old Excel format). "
            "Please convert to .xlsx or .xlsm. Supported formats: .csv, .xlsx, .xlsm"
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
        else:
            raise DataLoadError(
                f"Unsupported file format: {suffix}. Supported formats: .csv, .xlsx, .xlsm"
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


def write_data(df: pd.DataFrame, path: Path) -> None:
    """
    Write data to CSV or Excel file (XLSX/XLSM only).

    Args:
        df: DataFrame to write
        path: Output file path (.csv, .xlsx, or .xlsm)

    Raises:
        DataLoadError: If the file cannot be written or format is unsupported
        DependencyError: If Excel support is required but not installed
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
            "Please convert to .xlsx or .xlsm. Supported formats: .csv, .xlsx, .xlsm"
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

    raise DataLoadError(f"Unsupported file format: {suffix}. Supported formats: .csv, .xlsx, .xlsm")
