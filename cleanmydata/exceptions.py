"""Custom exceptions for the cleanmydata package."""


class CleanMyDataError(Exception):
    """Base exception for cleanmydata errors."""

    pass


class DataLoadError(CleanMyDataError):
    """Raised when data loading fails."""

    pass


class DataCleaningError(CleanMyDataError):
    """Raised when data cleaning operations fail."""

    pass
