"""Smoke tests for cleanmydata package."""

import builtins
from pathlib import Path

import pandas as pd
import pytest

import cleanmydata
import cleanmydata.clean as clean
from cleanmydata.clean import clean_data
from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import DependencyError
from cleanmydata.models import CleaningResult
from cleanmydata.utils.io import clean_file, read_data, write_data


def test_import_cleanmydata():
    """Test that cleanmydata can be imported."""
    assert cleanmydata is not None
    assert hasattr(cleanmydata, "__version__")


def test_import_cli():
    """Test that CLI module can be imported (only when cli extra is installed)."""
    pytest.importorskip("typer")
    import cleanmydata.cli  # noqa: F401

    assert cleanmydata.cli is not None
    assert hasattr(cleanmydata.cli, "app")


def test_read_data_reads_csv():
    """Test that read_data can read a CSV file."""
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)

    assert df is not None
    assert not df.empty
    assert len(df) > 0
    assert "name" in df.columns or "name" in [col.lower() for col in df.columns]


def test_clean_data_basic():
    """Test that clean_data function works on a simple dataset."""
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)

    cleaned_df, summary = clean_data(df, verbose=False)

    assert cleaned_df is not None
    assert not cleaned_df.empty
    assert isinstance(summary, dict)
    assert "rows" in summary
    assert "columns" in summary


def test_clean_data_reraises_original_exception(monkeypatch):
    boom = ValueError("boom")

    def explode(*args, **kwargs):
        raise boom

    monkeypatch.setattr(clean, "remove_duplicates", explode)

    df = pd.DataFrame({"a": [1, 2]})

    with pytest.raises(ValueError) as excinfo:
        clean_data(df, verbose=False)

    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "boom"


def test_clean_data_emits_no_settingwithcopywarning():
    """Ensure cleaning does not emit Pandas SettingWithCopyWarning."""
    import warnings

    from pandas.errors import SettingWithCopyWarning

    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", SettingWithCopyWarning)
        clean_data(df, verbose=False)

    assert not any(issubclass(w.category, SettingWithCopyWarning) for w in caught), (
        "clean_data emitted SettingWithCopyWarning"
    )


def test_excel_read_raises_dependencyerror_when_openpyxl_missing(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("forced missing openpyxl")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    xlsx_path = tmp_path / "input.xlsx"
    xlsx_path.write_bytes(b"not a real excel file; import should fail first")

    with pytest.raises(
        DependencyError,
        match=r'^Excel support is not installed\. Install with: pip install "cleanmydata\[excel\]"$',
    ):
        read_data(xlsx_path)


def test_excel_write_raises_dependencyerror_when_openpyxl_missing(monkeypatch, tmp_path):
    import pandas as pd

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("forced missing openpyxl")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    out_path = tmp_path / "output.xlsx"
    df = pd.DataFrame({"a": [1, 2]})

    with pytest.raises(
        DependencyError,
        match=r'^Excel support is not installed\. Install with: pip install "cleanmydata\[excel\]"$',
    ):
        write_data(df, out_path)


def test_clean_file_csv_happy_path(tmp_path):
    """Test clean_file with CSV file using default config."""
    # Use the existing fixture as input
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    output_path = tmp_path / "cleaned.csv"

    # Call clean_file
    result = clean_file(fixture_path, output_path)

    # Verify result is CleaningResult
    assert isinstance(result, CleaningResult)
    assert result.success
    assert result.rows > 0
    assert result.columns > 0

    # Verify output file was created
    assert output_path.exists()

    # Verify we can read it back
    df = read_data(output_path)
    assert not df.empty
    assert len(df) == result.rows


def test_clean_file_with_custom_config(tmp_path):
    """Test clean_file with custom CleaningConfig."""
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    output_path = tmp_path / "cleaned_custom.csv"

    # Create custom config
    config = CleaningConfig(
        outliers="remove",
        normalize_cols=False,
        clean_text=False,
        verbose=False,
    )

    # Call clean_file with custom config
    result = clean_file(fixture_path, output_path, config=config)

    # Verify result
    assert isinstance(result, CleaningResult)
    assert result.success
    assert result.rows > 0
    assert result.columns > 0

    # Verify output file was created
    assert output_path.exists()


def test_clean_file_file_not_found(tmp_path):
    """Test clean_file raises FileNotFoundError for non-existent file."""
    input_path = tmp_path / "nonexistent.csv"
    output_path = tmp_path / "output.csv"

    with pytest.raises(FileNotFoundError):
        clean_file(input_path, output_path)
