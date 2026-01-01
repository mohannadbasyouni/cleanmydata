"""CleanMyData - Public API exports."""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.1.0"

__all__ = [
    # Core functions
    "clean_data",
    "clean_file",
    "read_data",
    "write_data",
    # Configuration
    "CleaningConfig",
    # Results
    "CleaningResult",
    "ValidationResult",
    # Exceptions
    "CleanMyDataError",
    "DataLoadError",
    "DataCleaningError",
    "DependencyError",
    "ValidationError",
    "InvalidInputError",
    "CleanIOError",
    # Metadata
    "__version__",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    # Core functions
    "clean_data": ("cleanmydata.cleaning", "clean_data"),
    "clean_file": ("cleanmydata.utils.io", "clean_file"),
    "read_data": ("cleanmydata.utils.io", "read_data"),
    "write_data": ("cleanmydata.utils.io", "write_data"),
    # Configuration
    "CleaningConfig": ("cleanmydata.config", "CleaningConfig"),
    # Results
    "CleaningResult": ("cleanmydata.models", "CleaningResult"),
    "ValidationResult": ("cleanmydata.models", "ValidationResult"),
    # Exceptions
    "CleanMyDataError": ("cleanmydata.exceptions", "CleanMyDataError"),
    "DataLoadError": ("cleanmydata.exceptions", "DataLoadError"),
    "DataCleaningError": ("cleanmydata.exceptions", "DataCleaningError"),
    "DependencyError": ("cleanmydata.exceptions", "DependencyError"),
    "ValidationError": ("cleanmydata.exceptions", "ValidationError"),
    "InvalidInputError": ("cleanmydata.exceptions", "InvalidInputError"),
    "CleanIOError": ("cleanmydata.exceptions", "CleanIOError"),
}


def __getattr__(name: str) -> Any:
    """
    Lazy export loader to keep `import cleanmydata` lightweight.
    """

    target = _EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + __all__))
