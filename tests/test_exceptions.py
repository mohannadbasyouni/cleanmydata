"""Tests for the cleanmydata.exceptions module."""

from cleanmydata.exceptions import (
    CleanMyDataError,
    DataCleaningError,
    DataLoadError,
    DependencyError,
    StorageSigningError,
    ValidationError,
)


def test_all_exceptions_inherit_from_base():
    """Test that all custom exceptions inherit from CleanMyDataError."""
    exception_classes = [
        DependencyError,
        DataLoadError,
        DataCleaningError,
        ValidationError,
        StorageSigningError,
    ]

    for exc_class in exception_classes:
        assert issubclass(exc_class, CleanMyDataError)
        assert issubclass(exc_class, Exception)


def test_exception_messages():
    """Test that exceptions can be instantiated with custom messages."""
    message = "This is a test error message"

    # Test CleanMyDataError
    exc = CleanMyDataError(message)
    assert str(exc) == message

    # Test DependencyError
    exc = DependencyError(message)
    assert str(exc) == message

    # Test DataLoadError
    exc = DataLoadError(message)
    assert str(exc) == message

    # Test DataCleaningError
    exc = DataCleaningError(message)
    assert str(exc) == message

    # Test ValidationError
    exc = ValidationError(message)
    assert str(exc) == message

    # Test StorageSigningError
    exc = StorageSigningError(message)
    assert str(exc) == message
