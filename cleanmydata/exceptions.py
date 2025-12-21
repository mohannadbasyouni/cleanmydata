"""Custom exceptions for the cleanmydata package."""


class CleanMyDataError(Exception):
    """Base exception for cleanmydata errors."""

    pass


class DependencyError(CleanMyDataError):
    """Raised when an optional dependency is required but not installed."""

    pass


class DataLoadError(CleanMyDataError):
    """Raised when data loading fails."""

    pass


class DataCleaningError(CleanMyDataError):
    """Raised when data cleaning operations fail."""

    pass


class ValidationError(CleanMyDataError):
    """Raised when configuration validation fails."""

    pass
