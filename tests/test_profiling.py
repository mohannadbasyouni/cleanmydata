from pathlib import Path

from cleanmydata.cleaning import clean_data
from cleanmydata.utils.io import read_data


def test_clean_data_profiling_is_opt_in():
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)

    _, summary_default = clean_data(df, verbose=False)
    assert "profiling" not in summary_default

    _, summary_profiled = clean_data(df, verbose=False, profile=True)
    assert "profiling" in summary_profiled

    profiling = summary_profiled["profiling"]
    assert isinstance(profiling, dict)
    assert "total_ms" in profiling
    assert "steps" in profiling
    assert isinstance(profiling["steps"], dict)

    steps = profiling["steps"]
    for expected_step in {
        "remove_duplicates",
        "normalize_columns",
        "clean_text",
        "standardize_formats",
        "handle_outliers",
        "fill_missing",
    }:
        assert expected_step in steps
