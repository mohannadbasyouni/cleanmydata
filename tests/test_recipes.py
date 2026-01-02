import pytest

from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import ValidationError
from cleanmydata.recipes import load_recipe, save_recipe


def test_load_valid_recipe(tmp_path):
    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text(
        "\n".join(
            [
                "outliers: cap",
                "normalize_cols: true",
                "clean_text: false",
                "auto_outlier_detect: true",
            ]
        ),
        encoding="utf-8",
    )

    recipe = load_recipe(recipe_path)
    assert recipe.outliers == "cap"
    assert recipe.normalize_cols is True
    assert recipe.clean_text is False
    assert recipe.auto_outlier_detect is True


def test_save_recipe_creates_yaml(tmp_path):
    recipe_path = tmp_path / "saved.yml"
    config = CleaningConfig(
        outliers="remove",
        normalize_cols=False,
        clean_text=True,
        auto_outlier_detect=False,
    )
    save_recipe(config, recipe_path)
    assert recipe_path.exists()


def test_recipe_roundtrip(tmp_path):
    recipe_path = tmp_path / "roundtrip.yml"
    config = CleaningConfig(
        outliers=None,
        normalize_cols=False,
        clean_text=False,
        auto_outlier_detect=True,
    )
    save_recipe(config, recipe_path)
    loaded = load_recipe(recipe_path)

    assert loaded.outliers is None
    assert loaded.normalize_cols is False
    assert loaded.clean_text is False
    assert loaded.auto_outlier_detect is True


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
    recipe_path.write_text("unknown_field: true", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_recipe(recipe_path)


def test_missing_recipe_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "missing.yml"
    with pytest.raises(FileNotFoundError):
        load_recipe(missing)


def test_save_recipe_missing_directory_raises_file_not_found(tmp_path):
    missing_dir = tmp_path / "missing_dir"
    recipe_path = missing_dir / "recipe.yml"
    with pytest.raises(FileNotFoundError):
        save_recipe(CleaningConfig(), recipe_path)
