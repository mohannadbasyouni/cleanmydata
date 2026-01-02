"""Pydantic model for CLI options."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
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
    profile: bool = False

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: Path) -> Path:
        if not str(value).strip():
            raise ValueError("path must be provided")

        suffix = value.suffix.lower()
        if not suffix:
            return value.with_suffix(".csv")
        if suffix not in SUPPORTED_FORMATS:
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
        suffix = value.suffix.lower()
        if not suffix:
            raise ValueError(
                f"output must include a supported file extension {sorted(SUPPORTED_FORMATS)}"
            )
        if suffix not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported output file format: {suffix}. Supported formats: {sorted(SUPPORTED_FORMATS)}"
            )
        return value

    @field_validator("outliers")
    @classmethod
    def _validate_outliers(
        cls, value: Literal["cap", "remove", None]
    ) -> Literal["cap", "remove", None]:
        if value not in OUTLIER_METHODS:
            raise ValueError(f"outliers must be one of {OUTLIER_METHODS}")
        return value

    @model_validator(mode="after")
    def _normalize_output_modes(self) -> CLIConfig:
        if self.silent:
            object.__setattr__(self, "quiet", False)
            object.__setattr__(self, "verbose", False)
        elif self.quiet:
            object.__setattr__(self, "verbose", False)
        return self

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
            profile=self.profile,
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

    @classmethod
    def from_sources(
        cls,
        cli_args: Mapping[str, Any],
        config_path: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
        recipe_path: str | Path | None = None,
    ) -> CLIConfig:
        """
        Merge config from recipe, YAML, environment, then CLI, respecting precedence.
        """
        merged: dict[str, Any] = {}

        if recipe_path:
            from cleanmydata.recipes import load_recipe

            recipe = load_recipe(Path(recipe_path))
            merged.update(
                {
                    "outliers": recipe.outliers,
                    "normalize_cols": recipe.normalize_cols,
                    "clean_text": recipe.clean_text,
                    "auto_outlier_detect": recipe.auto_outlier_detect,
                    "profile": recipe.profile,
                }
            )

        if config_path:
            merged.update(cls._load_yaml_config(config_path))

        env_values = cls._load_env_vars(environ or {})
        merged.update(env_values)

        cli_overrides = {key: value for key, value in cli_args.items() if value is not None}
        merged.update(cli_overrides)

        return cls.from_cli(**merged)

    @staticmethod
    def _parse_bool(value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValidationError(f"Invalid boolean value: {value!r}")

    @staticmethod
    def _parse_outliers(value: str) -> Literal["cap", "remove", None]:
        normalized = value.strip().lower()
        if normalized == "none":
            return None
        if normalized in {"cap", "remove"}:
            return normalized  # type: ignore[return-value]
        raise ValidationError(f"Invalid outliers value: {value!r} (expected cap, remove, or none)")

    @classmethod
    def _load_env_vars(cls, environ: Mapping[str, str]) -> dict[str, Any]:
        env_map: dict[str, str] = {
            "CLEANMYDATA_PATH": "path",
            "CLEANMYDATA_OUTPUT": "output",
            "CLEANMYDATA_VERBOSE": "verbose",
            "CLEANMYDATA_QUIET": "quiet",
            "CLEANMYDATA_SILENT": "silent",
            "CLEANMYDATA_LOG": "log",
            "CLEANMYDATA_OUTLIERS": "outliers",
            "CLEANMYDATA_NORMALIZE_COLS": "normalize_cols",
            "CLEANMYDATA_CLEAN_TEXT": "clean_text",
            "CLEANMYDATA_AUTO_OUTLIER_DETECT": "auto_outlier_detect",
            "CLEANMYDATA_PROFILE": "profile",
        }

        parsed: dict[str, Any] = {}
        for env_var, field_name in env_map.items():
            if env_var not in environ:
                continue
            raw_value = environ[env_var]
            try:
                if field_name in {
                    "verbose",
                    "quiet",
                    "silent",
                    "log",
                    "normalize_cols",
                    "clean_text",
                    "auto_outlier_detect",
                    "profile",
                }:
                    parsed[field_name] = cls._parse_bool(raw_value)
                elif field_name == "outliers":
                    parsed[field_name] = cls._parse_outliers(raw_value)
                else:
                    parsed[field_name] = raw_value
            except ValidationError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                raise ValidationError(str(exc)) from exc
        return parsed

    @staticmethod
    def _load_yaml_config(path: str | Path) -> dict[str, Any]:
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with config_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid YAML in config file: {exc}") from exc

        if not isinstance(data, dict):
            raise ValidationError("Config file must contain a top-level mapping")

        return data
