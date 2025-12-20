"""Core I/O functions for reading and writing data files."""

from pathlib import Path

import pandas as pd

from cleanmydata.constants import SUPPORTED_FORMATS
from cleanmydata.exceptions import DataLoadError


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
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    # Explicitly reject .xls (old Excel format)
    if suffix == ".xls":
        raise DataLoadError(
            "Unsupported file format: .xls (old Excel format). "
            f"Please convert to .xlsx or .xlsm. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )

    try:
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".xlsx", ".xlsm"):
            df = pd.read_excel(path)
        else:
            raise DataLoadError(
                f"Unsupported file format: {suffix}. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )

        return df

    except pd.errors.EmptyDataError as e:
        raise DataLoadError(f"The file is empty or invalid: {path}") from e
    except pd.errors.ParserError as e:
        raise DataLoadError(f"Parsing error occurred while reading the file: {path}") from e
    except Exception as e:
        raise DataLoadError(f"Unexpected error while loading file {path}: {e}") from e
