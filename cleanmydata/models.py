"""Data models for the cleanmydata package."""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """
    Result of a validation operation.

    Success is determined by the absence of errors, not warnings.
    Warnings are informational and do not indicate failure.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def failed(self) -> bool:
        """True if validation failed (has errors)."""
        return len(self.errors) > 0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)


@dataclass
class CleaningResult:
    """
    Result of a data cleaning operation.

    Success is determined by the absence of errors, not warnings.
    Contains summary statistics and any errors/warnings encountered.
    """

    rows: int = 0
    columns: int = 0
    duplicates_removed: int = 0
    outliers_handled: int = 0
    missing_filled: int = 0
    columns_standardized: int = 0
    text_unconverted: int = 0
    duration: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if cleaning succeeded (no errors)."""
        return len(self.errors) == 0

    @property
    def failed(self) -> bool:
        """True if cleaning failed (has errors)."""
        return len(self.errors) > 0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def to_dict(self) -> dict:
        """Convert result to dictionary format."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "duplicates_removed": self.duplicates_removed,
            "outliers_handled": self.outliers_handled,
            "missing_filled": self.missing_filled,
            "columns_standardized": self.columns_standardized,
            "text_unconverted": self.text_unconverted,
            "duration": self.duration,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class Suggestion:
    """
    Structured AI suggestion for data quality improvements.

    Advisory-only: never used to mutate data automatically.
    """

    category: str
    severity: str
    message: str
    column: str | None = None
    evidence: dict | None = None

    def to_dict(self) -> dict:
        """Convert suggestion to a serializable dict."""
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "column": self.column,
            "evidence": self.evidence,
        }
