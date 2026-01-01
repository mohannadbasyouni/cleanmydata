"""Tests for the cleanmydata.utils.io module."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import pytest

from cleanmydata.exceptions import DataLoadError, DependencyError
from cleanmydata.utils.io import read_data, write_data


def test_read_data_csv_success():
    """Test successfully reading a CSV file."""
    # Use the existing test fixture
    csv_path = Path("tests/fixtures/small.csv")

    df = read_data(csv_path)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "name" in df.columns
    assert "age" in df.columns
    assert "city" in df.columns
    assert "price" in df.columns


def test_read_data_file_not_found():
    """Test that reading a non-existent file raises FileNotFoundError."""
    non_existent_path = Path("tests/fixtures/nonexistent.csv")

    with pytest.raises(FileNotFoundError):
        read_data(non_existent_path)


def test_read_data_unsupported_format():
    """Test that reading an unsupported file format raises DataLoadError."""
    # Create a temporary file with unsupported extension
    with NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        with pytest.raises(DataLoadError) as exc_info:
            read_data(temp_path)

        assert "Unsupported file format" in str(exc_info.value)
        assert ".txt" in str(exc_info.value)
    finally:
        temp_path.unlink()


def test_read_data_xls_rejected():
    """Test that reading .xls files raises DataLoadError with helpful message."""
    # Create a temporary .xls file
    with NamedTemporaryFile(suffix=".xls", delete=False, mode="w") as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        with pytest.raises(DataLoadError) as exc_info:
            read_data(temp_path)

        assert "Unsupported file format: .xls" in str(exc_info.value)
        assert "old Excel format" in str(exc_info.value)
        assert "convert to .xlsx or .xlsm" in str(exc_info.value)
    finally:
        temp_path.unlink()


def test_write_data_csv_success():
    """Test successfully writing data to a CSV file."""
    # Create a simple DataFrame
    df = pd.DataFrame(
        {"name": ["Alice", "Bob"], "age": [25, 30], "city": ["New York", "Los Angeles"]}
    )

    with NamedTemporaryFile(suffix=".csv", delete=False) as f:
        temp_path = Path(f.name)

    try:
        write_data(df, temp_path)

        # Verify the file was written correctly
        df_read = pd.read_csv(temp_path)
        assert len(df_read) == 2
        assert list(df_read.columns) == ["name", "age", "city"]
        assert df_read["name"].tolist() == ["Alice", "Bob"]
    finally:
        temp_path.unlink()


def test_write_data_xls_rejected():
    """Test that writing to .xls files raises DataLoadError with helpful message."""
    df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})

    with NamedTemporaryFile(suffix=".xls", delete=False) as f:
        temp_path = Path(f.name)

    try:
        with pytest.raises(DataLoadError) as exc_info:
            write_data(df, temp_path)

        assert "Unsupported file format: .xls" in str(exc_info.value)
        assert "old Excel format" in str(exc_info.value)
        assert "convert to .xlsx or .xlsm" in str(exc_info.value)
    finally:
        temp_path.unlink()


def test_parquet_roundtrip(tmp_path: Path):
    """Test reading and writing Parquet files when dependency is available."""
    pytest.importorskip("pyarrow")

    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    path = tmp_path / "data.parquet"

    write_data(df, path)
    result = read_data(path)

    pd.testing.assert_frame_equal(result, df, check_dtype=False)


def test_read_data_parquet_missing_dependency(monkeypatch, tmp_path: Path):
    """read_data raises DependencyError when Parquet engine is unavailable."""
    path = tmp_path / "data.parquet"
    path.touch()

    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError("engine missing")),
    )

    with pytest.raises(DependencyError) as exc_info:
        read_data(path)

    assert "cleanmydata[parquet]" in str(exc_info.value)


def test_write_data_parquet_missing_dependency(monkeypatch, tmp_path: Path):
    """write_data raises DependencyError when Parquet engine is unavailable."""
    df = pd.DataFrame({"a": [1, 2]})
    path = tmp_path / "data.parquet"

    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError("engine missing")),
    )

    with pytest.raises(DependencyError) as exc_info:
        write_data(df, path)

    assert "cleanmydata[parquet]" in str(exc_info.value)
