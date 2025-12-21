"""Smoke tests for cleanmydata package."""

from pathlib import Path

import cleanmydata
from cleanmydata.clean import clean_data
from cleanmydata.utils.io import read_data


def test_import_cleanmydata():
    """Test that cleanmydata can be imported."""
    assert cleanmydata is not None
    assert hasattr(cleanmydata, "__version__")


def test_import_cli():
    """Test that CLI module can be imported."""
    import cleanmydata.cli

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
