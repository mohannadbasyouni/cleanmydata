"""Tests for the cleanmydata.exceptions module."""

from cleanmydata.exceptions import (
    CleanIOError,
    CleanMyDataError,
    DataCleaningError,
    DataLoadError,
    DependencyError,
    InvalidInputError,
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
        InvalidInputError,
        CleanIOError,
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

    # Test InvalidInputError
    exc = InvalidInputError(message)
    assert str(exc) == message

    # Test CleanIOError
    exc = CleanIOError(message)
    assert str(exc) == message
