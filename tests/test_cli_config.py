from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from cleanmydata.cli_config import CLIConfig
from cleanmydata.config import CleaningConfig
from cleanmydata.constants import (
    DEFAULT_AUTO_OUTLIER_DETECT,
    DEFAULT_CLEAN_TEXT,
    DEFAULT_NORMALIZE_COLS,
    DEFAULT_OUTLIER_METHOD,
)


def test_cli_config_accepts_valid_values_and_defaults(tmp_path: Path) -> None:
    cfg = CLIConfig(path=tmp_path / "input.csv")

    assert cfg.output is None
    assert cfg.verbose is False
    assert cfg.quiet is False
    assert cfg.silent is False
    assert cfg.log is False
    assert cfg.profile is False

    assert cfg.outliers == DEFAULT_OUTLIER_METHOD
    assert cfg.normalize_cols is DEFAULT_NORMALIZE_COLS
    assert cfg.clean_text is DEFAULT_CLEAN_TEXT
    assert cfg.auto_outlier_detect is DEFAULT_AUTO_OUTLIER_DETECT
    assert cfg.categorical_mapping is None


def test_cli_config_invalid_outliers_raises_pydantic_validation_error(tmp_path: Path) -> None:
    with pytest.raises(PydanticValidationError) as exc_info:
        CLIConfig(path=tmp_path / "input.csv", outliers="bogus")  # type: ignore[arg-type]

    message = str(exc_info.value).lower()
    assert "outliers" in message


def test_cli_config_from_sources_precedence_recipe_yaml_env_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verify merge order is recipe < yaml < env < cli.

    We patch recipe loading to keep this test independent of recipe/YAML extras
    and to avoid duplicating recipe schema tests.
    """

    import cleanmydata.recipes as recipes

    def fake_load_recipe(_: Path) -> CleaningConfig:
        return CleaningConfig(outliers="remove")

    monkeypatch.setattr(recipes, "load_recipe", fake_load_recipe)

    config_path = tmp_path / "config.yml"
    config_path.write_text("outliers: cap\n", encoding="utf-8")

    # YAML overrides recipe.
    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv"},
        recipe_path=tmp_path / "recipe.yml",
        config_path=config_path,
        environ={},
    )
    assert cfg.outliers == "cap"

    # Env overrides YAML.
    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv"},
        recipe_path=tmp_path / "recipe.yml",
        config_path=config_path,
        environ={"CLEANMYDATA_OUTLIERS": "none"},
    )
    assert cfg.outliers is None

    # CLI overrides env.
    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv", "outliers": "remove"},
        recipe_path=tmp_path / "recipe.yml",
        config_path=config_path,
        environ={"CLEANMYDATA_OUTLIERS": "none"},
    )
    assert cfg.outliers == "remove"
