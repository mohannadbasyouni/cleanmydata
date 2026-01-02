"""Save and load cleaning recipes (YAML configurations)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import ValidationError as PydanticValidationError

from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import DependencyError, ValidationError

RecipeOutliers = Literal["cap", "remove", None]


def _import_yaml():
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DependencyError(
            'YAML support requires CLI extra. Install with: pip install "cleanmydata[cli]"'
        ) from exc
    return yaml


class RecipeYaml(BaseModel):
    """
    Validated recipe schema (plan Phase 9.2).

    Keys are intentionally limited to cleaning config fields only.
    """

    model_config = ConfigDict(extra="forbid")

    outliers: RecipeOutliers = None
    normalize_cols: bool | None = None
    clean_text: bool | None = None
    auto_outlier_detect: bool | None = None

    @field_validator("outliers", mode="before")
    @classmethod
    def _normalize_outliers(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "none":
                return None
            if normalized in {"cap", "remove"}:
                return normalized
        return value

    def as_cleaning_kwargs(self) -> dict[str, Any]:
        """
        Return kwargs compatible with CleaningConfig.

        Uses field-set information so explicit `outliers: none` (normalized to None)
        still overrides CleaningConfig defaults.
        """
        allowed = {"outliers", "normalize_cols", "clean_text", "auto_outlier_detect"}
        return {key: getattr(self, key) for key in self.model_fields_set if key in allowed}


def save_recipe(config: CleaningConfig, path: Path) -> None:
    """
    Save a CleaningConfig as a YAML recipe file (plan Phase 9.2 schema).

    Raises:
        DependencyError: If PyYAML not installed (should be with cli extra)
        ValidationError: If config is invalid
        FileNotFoundError: If destination directory does not exist
        IsADirectoryError: If path points to a directory
    """
    yaml = _import_yaml()

    try:
        config.validate()
    except ValidationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ValidationError(str(exc)) from exc

    recipe_path = Path(path)
    if recipe_path.exists() and recipe_path.is_dir():
        raise IsADirectoryError(f"Recipe path is a directory: {recipe_path}")
    if recipe_path.parent and not recipe_path.parent.exists():
        raise FileNotFoundError(f"Recipe directory not found: {recipe_path.parent}")

    outliers: str | None = config.outliers
    if outliers is None:
        outliers_value: str | None = "none"
    else:
        outliers_value = str(outliers)

    data = {
        "outliers": outliers_value,
        "normalize_cols": config.normalize_cols,
        "clean_text": config.clean_text,
        "auto_outlier_detect": config.auto_outlier_detect,
    }

    try:
        with recipe_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False)
    except OSError as exc:
        # Let CLI map this to an IO exit code.
        raise exc


def load_recipe(path: Path) -> CleaningConfig:
    """Load and validate a recipe from YAML.

    Raises:
        FileNotFoundError: if the recipe file is missing
        ValidationError: if YAML is invalid or does not match the schema
    """
    yaml = _import_yaml()

    recipe_path = Path(path)
    if not recipe_path.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")

    try:
        with recipe_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in recipe file: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError("Recipe file must contain a top-level mapping")

    try:
        parsed = RecipeYaml(**data)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc)) from exc

    config = CleaningConfig(**parsed.as_cleaning_kwargs())
    try:
        config.validate()
    except ValidationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ValidationError(str(exc)) from exc
    return config
