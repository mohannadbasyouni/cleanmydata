"""Pydantic model for CLI options."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError

from cleanmydata.config import CleaningConfig
from cleanmydata.constants import (
    DEFAULT_AUTO_OUTLIER_DETECT,
    DEFAULT_CLEAN_TEXT,
    DEFAULT_NORMALIZE_COLS,
    DEFAULT_OUTLIER_METHOD,
    OUTLIER_METHODS,
    SUPPORTED_FORMATS,
)
from cleanmydata.exceptions import ValidationError


class CLIConfig(BaseModel):
    """Validated representation of CLI options."""

    model_config = ConfigDict(extra="forbid")

    path: Path = Field(..., description="Input dataset path")
    output: Path | None = Field(
        default=None, description="Optional output file path (defaults to data/<name>_cleaned.ext)"
    )
    verbose: bool = False
    quiet: bool = False
    silent: bool = False
    log: bool = False

    # Cleaning config fields (kept here to keep CLI defaults in sync with core)
    outliers: Literal["cap", "remove", None] = DEFAULT_OUTLIER_METHOD
    normalize_cols: bool = DEFAULT_NORMALIZE_COLS
    clean_text: bool = DEFAULT_CLEAN_TEXT
    auto_outlier_detect: bool = DEFAULT_AUTO_OUTLIER_DETECT
    categorical_mapping: dict[str, dict[str, str]] | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: Path) -> Path:
        if not str(value).strip():
            raise ValueError("path must be provided")

        suffix = value.suffix.lower()
        if suffix and suffix not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {suffix}. Supported formats: {sorted(SUPPORTED_FORMATS)}"
            )
        return value

    @field_validator("output")
    @classmethod
    def _validate_output(cls, value: Path | None) -> Path | None:
        if value is None:
            return value
        if not str(value).strip():
            raise ValueError("output must not be empty")
        return value

    @field_validator("outliers")
    @classmethod
    def _validate_outliers(
        cls, value: Literal["cap", "remove", None]
    ) -> Literal["cap", "remove", None]:
        if value not in OUTLIER_METHODS:
            raise ValueError(f"outliers must be one of {OUTLIER_METHODS}")
        return value

    def to_cleaning_config(self) -> CleaningConfig:
        """
        Convert to core CleaningConfig and validate.

        Raises:
            ValidationError: if generated CleaningConfig is invalid
        """
        config = CleaningConfig(
            outliers=self.outliers,
            normalize_cols=self.normalize_cols,
            clean_text=self.clean_text,
            categorical_mapping=self.categorical_mapping,
            auto_outlier_detect=self.auto_outlier_detect,
            verbose=self.verbose,
        )
        try:
            config.validate()
        except ValidationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise ValidationError(str(exc)) from exc
        return config

    @classmethod
    def from_cli(cls, **kwargs) -> CLIConfig:
        """
        Build from CLI args, normalizing validation errors to package ValidationError.
        """
        try:
            return cls(**kwargs)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc
