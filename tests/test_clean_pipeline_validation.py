import pandas as pd
import pytest

from cleanmydata.clean import clean_data, normalize_column_names
from cleanmydata.exceptions import InvalidInputError


def test_normalize_column_names_handles_int_columns():
    df = pd.DataFrame({1: [1], 2: [2]})
    normalized = normalize_column_names(df.copy())
    assert list(normalized.columns) == ["1", "2"]


def test_normalize_column_names_handles_mixed_type_columns():
    df = pd.DataFrame({" A ": [1], 2: [2], "b b": [3]})
    normalized = normalize_column_names(df.copy())
    assert list(normalized.columns) == ["a", "2", "b_b"]


def test_clean_data_rejects_invalid_outliers_value():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 100]})
    with pytest.raises(InvalidInputError):
        clean_data(
            df,
            outliers="bogus",
            normalize_cols=False,
            clean_text=False,
            auto_outlier_detect=False,
        )


def test_clean_data_outliers_cap_and_remove_behave_as_expected():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 100]})

    capped, _ = clean_data(
        df.copy(),
        outliers="cap",
        normalize_cols=False,
        clean_text=False,
        auto_outlier_detect=False,
    )
    assert float(capped["x"].max()) == 7.0

    removed, summary = clean_data(
        df.copy(),
        outliers="remove",
        normalize_cols=False,
        clean_text=False,
        auto_outlier_detect=False,
    )
    assert len(removed) == 4
    assert summary["outliers_handled"] == 1


def test_clean_data_empty_input_raises():
    df = pd.DataFrame({"a": []})
    with pytest.raises(InvalidInputError):
        clean_data(df, normalize_cols=False, clean_text=False)
