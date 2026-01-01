import pytest

from cleanmydata.exceptions import ValidationError
from cleanmydata.recipes import Recipe, load_recipe


def test_load_valid_recipe(tmp_path):
    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text(
        "\n".join(
            [
                "name: Basic",
                "description: Demo recipe",
                "outliers: cap",
                "normalize_cols: true",
                "clean_text: false",
                "auto_outlier_detect: true",
                "categorical_mapping:",
                "  country:",
                "    usa: US",
            ]
        ),
        encoding="utf-8",
    )

    recipe = load_recipe(recipe_path)
    assert isinstance(recipe, Recipe)
    assert recipe.name == "Basic"
    assert recipe.outliers == "cap"
    assert recipe.normalize_cols is True
    assert recipe.clean_text is False
    assert recipe.auto_outlier_detect is True
    assert recipe.categorical_mapping == {"country": {"usa": "US"}}


def test_invalid_yaml_raises_validation_error(tmp_path):
    recipe_path = tmp_path / "bad.yml"
    recipe_path.write_text(":\n  - bad", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_recipe(recipe_path)


def test_non_mapping_yaml_raises_validation_error(tmp_path):
    recipe_path = tmp_path / "list.yml"
    recipe_path.write_text("- a\n- b", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_recipe(recipe_path)


def test_unknown_key_rejected(tmp_path):
    recipe_path = tmp_path / "unknown.yml"
    recipe_path.write_text("name: Test\nunknown_field: true", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_recipe(recipe_path)


def test_missing_recipe_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "missing.yml"
    with pytest.raises(FileNotFoundError):
        load_recipe(missing)
