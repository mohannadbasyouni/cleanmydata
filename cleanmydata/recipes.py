"""Recipe schema and loader for YAML cleaning presets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from cleanmydata.exceptions import ValidationError

RecipeOutliers = Literal["cap", "remove", None]


class Recipe(BaseModel):
    """Validated cleaning recipe."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    outliers: RecipeOutliers = None
    normalize_cols: bool | None = None
    clean_text: bool | None = None
    auto_outlier_detect: bool | None = None
    categorical_mapping: dict[str, dict[str, str]] | None = None

    def cleaning_options(self) -> dict[str, Any]:
        """Return only cleaning-relevant options, excluding metadata."""

        allowed_fields = {
            "outliers",
            "normalize_cols",
            "clean_text",
            "auto_outlier_detect",
            "categorical_mapping",
        }
        return {
            key: value
            for key, value in self.model_dump(exclude_none=True).items()
            if key in allowed_fields
        }


def load_recipe(path: Path) -> Recipe:
    """Load and validate a recipe from YAML.

    Raises:
        FileNotFoundError: if the recipe file is missing
        ValidationError: if YAML is invalid or does not match the schema
    """

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
        return Recipe(**data)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc)) from exc
