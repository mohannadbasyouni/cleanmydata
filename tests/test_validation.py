from pathlib import Path

import pandas as pd
import pytest

from cleanmydata.exceptions import DependencyError, ValidationError
from cleanmydata.validation import schema as schema_module


def _write_schema(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "schema.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_schema_passes(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
                "    nullable: false",
                "  name:",
                "    dtype: str",
                "    required: true",
            ]
        ),
    )
    df = pd.DataFrame({"age": [10, 20], "name": ["a", "b"]})

    schema = schema_module.load_schema(schema_path)
    schema_module.validate_df(df, schema)


def test_missing_required_column_fails(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
                "    required: true",
            ]
        ),
    )
    df = pd.DataFrame({"name": ["a"]})

    schema = schema_module.load_schema(schema_path)
    with pytest.raises(ValidationError):
        schema_module.validate_df(df, schema)


def test_optional_column_missing_passes(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  note:",
                "    dtype: str",
                "    required: false",
            ]
        ),
    )
    df = pd.DataFrame({"name": ["a"]})

    schema = schema_module.load_schema(schema_path)
    schema_module.validate_df(df, schema)


def test_dtype_mismatch_fails(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
            ]
        ),
    )
    df = pd.DataFrame({"age": ["not-int"]})

    schema = schema_module.load_schema(schema_path)
    with pytest.raises(ValidationError):
        schema_module.validate_df(df, schema)


def test_check_in_range_fails(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
                "    checks:",
                "      - in_range:",
                "          min: 0",
                "          max: 120",
            ]
        ),
    )
    df = pd.DataFrame({"age": [150]})

    schema = schema_module.load_schema(schema_path)
    with pytest.raises(ValidationError):
        schema_module.validate_df(df, schema)


def test_check_isin_fails(tmp_path):
    schema_path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  status:",
                "    dtype: str",
                "    checks:",
                "      - isin: [open, closed]",
            ]
        ),
    )
    df = pd.DataFrame({"status": ["pending"]})

    schema = schema_module.load_schema(schema_path)
    with pytest.raises(ValidationError):
        schema_module.validate_df(df, schema)


def test_invalid_yaml_raises_validationerror(tmp_path):
    path = _write_schema(tmp_path, ":\n  - bad")
    with pytest.raises(ValidationError):
        schema_module.load_schema(path)


def test_yaml_not_mapping_raises_validationerror(tmp_path):
    path = _write_schema(tmp_path, "- a\n- b")
    with pytest.raises(ValidationError):
        schema_module.load_schema(path)


def test_unknown_keys_rejected(tmp_path):
    path = _write_schema(tmp_path, "columns: {}\nunknown: true")
    with pytest.raises(ValidationError):
        schema_module.load_schema(path)


def test_missing_pandera_dependency(monkeypatch, tmp_path):
    path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
            ]
        ),
    )

    import importlib

    original_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "pandera":
            raise ImportError("pandera missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    with pytest.raises(DependencyError) as exc:
        schema_module.load_schema(path)

    assert "cleanmydata[schema]" in str(exc.value)
