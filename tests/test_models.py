"""Tests for the cleanmydata.models module."""

from cleanmydata.models import CleaningResult, ValidationResult


def test_validation_result_success_no_errors():
    """Test ValidationResult with no errors is considered successful."""
    result = ValidationResult()

    assert result.success is True
    assert result.failed is False
    assert len(result.errors) == 0
    assert len(result.warnings) == 0


def test_validation_result_failed_with_errors():
    """Test ValidationResult with errors is considered failed."""
    result = ValidationResult()
    result.add_error("Test error 1")
    result.add_error("Test error 2")

    assert result.success is False
    assert result.failed is True
    assert len(result.errors) == 2
    assert "Test error 1" in result.errors
    assert "Test error 2" in result.errors


def test_validation_result_success_with_warnings():
    """Test ValidationResult with only warnings is still considered successful."""
    result = ValidationResult()
    result.add_warning("Test warning 1")
    result.add_warning("Test warning 2")

    assert result.success is True
    assert result.failed is False
    assert len(result.errors) == 0
    assert len(result.warnings) == 2
    assert "Test warning 1" in result.warnings
    assert "Test warning 2" in result.warnings


def test_cleaning_result_success_property():
    """Test CleaningResult success property based on presence of errors."""
    # Test success with no errors
    result = CleaningResult(rows=100, columns=5)
    assert result.success is True
    assert result.failed is False

    # Test failure with errors
    result = CleaningResult(rows=100, columns=5)
    result.add_error("Test error")
    assert result.success is False
    assert result.failed is True

    # Test success with warnings only
    result = CleaningResult(rows=100, columns=5)
    result.add_warning("Test warning")
    assert result.success is True
    assert result.failed is False


def test_cleaning_result_to_dict():
    """Test CleaningResult to_dict method produces correct dictionary."""
    result = CleaningResult(
        rows=100,
        columns=5,
        duplicates_removed=10,
        outliers_handled=5,
        missing_filled=3,
        columns_standardized=2,
        text_unconverted=1,
        duration="1.5s",
    )
    result.add_error("Test error")
    result.add_warning("Test warning")

    result_dict = result.to_dict()

    assert result_dict["rows"] == 100
    assert result_dict["columns"] == 5
    assert result_dict["duplicates_removed"] == 10
    assert result_dict["outliers_handled"] == 5
    assert result_dict["missing_filled"] == 3
    assert result_dict["columns_standardized"] == 2
    assert result_dict["text_unconverted"] == 1
    assert result_dict["duration"] == "1.5s"
    assert len(result_dict["errors"]) == 1
    assert "Test error" in result_dict["errors"]
    assert len(result_dict["warnings"]) == 1
    assert "Test warning" in result_dict["warnings"]
