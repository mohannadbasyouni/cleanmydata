"""Smoke tests for cleanmydata package."""

import builtins
from pathlib import Path

import pytest

import cleanmydata
from cleanmydata.clean import clean_data
from cleanmydata.exceptions import DependencyError
from cleanmydata.utils.io import read_data, write_data


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
