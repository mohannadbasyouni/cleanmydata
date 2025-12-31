"""Tests for the cleanmydata.config module."""

import pytest

from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import ValidationError


def test_cleaning_config_defaults():
    """Test that CleaningConfig has correct default values."""
    config = CleaningConfig()

    assert config.outliers == "cap"
    assert config.normalize_cols is True
    assert config.clean_text is True
    assert config.categorical_mapping is None
    assert config.auto_outlier_detect is True
    assert config.verbose is False


def test_cleaning_config_validate_valid_outlier():
    """Test that validate() passes for valid outlier methods."""
    # Test all valid outlier methods
    valid_methods = ["cap", "remove", None]

    for method in valid_methods:
        config = CleaningConfig(outliers=method)
        config.validate()  # Should not raise


def test_cleaning_config_validate_invalid_outlier():
    """Test that validate() raises ValidationError for invalid outlier method."""
    config = CleaningConfig(outliers="invalid_method")

    with pytest.raises(ValidationError) as exc_info:
        config.validate()

    assert "Invalid outlier method" in str(exc_info.value)
    assert "invalid_method" in str(exc_info.value)


def test_cleaning_config_validate_invalid_categorical_mapping():
    """Test that validate() raises ValidationError for invalid categorical_mapping."""
    # Test with non-dict categorical_mapping
    config = CleaningConfig(categorical_mapping="not_a_dict")

    with pytest.raises(ValidationError) as exc_info:
        config.validate()

    assert "categorical_mapping must be a dictionary" in str(exc_info.value)

    # Test with dict that contains non-dict values
    config = CleaningConfig(categorical_mapping={"col1": "not_a_dict"})

    with pytest.raises(ValidationError) as exc_info:
        config.validate()

    assert "must be a dictionary mapping old to new values" in str(exc_info.value)
    assert "col1" in str(exc_info.value)
