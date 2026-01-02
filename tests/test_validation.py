import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError as PydanticValidationError

from cleanmydata.exceptions import DependencyError, ValidationError
from cleanmydata.validation import schema as schema_module

PANDERA_AVAILABLE = importlib.util.find_spec("pandera") is not None


def _write_schema(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "schema.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_schema_passes(tmp_path):
    pytest.importorskip("pandera")
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
    pytest.importorskip("pandera")
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
    pytest.importorskip("pandera")
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
    pytest.importorskip("pandera")
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
    pytest.importorskip("pandera")
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
    pytest.importorskip("pandera")
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


def test_invalid_yaml_raises_validationerror(monkeypatch, tmp_path):
    # Lock YAML parsing behavior even when pandera is not installed.
    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())
    path = _write_schema(tmp_path, ":\n  - bad")
    with pytest.raises(ValidationError, match=r"Invalid YAML in schema file:"):
        schema_module.load_schema(path)


def test_yaml_not_mapping_raises_validationerror(monkeypatch, tmp_path):
    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())
    path = _write_schema(tmp_path, "- a\n- b")
    with pytest.raises(ValidationError, match=r"top-level mapping"):
        schema_module.load_schema(path)


def test_unknown_keys_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())
    path = _write_schema(tmp_path, "columns: {}\nunknown: true")
    with pytest.raises(ValidationError):
        schema_module.load_schema(path)


def test_invalid_schema_structure_surfaces_pydantic_details(monkeypatch, tmp_path):
    # Lock "invalid structure" (schema spec validation) behavior independently of pandera.
    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())
    path = _write_schema(
        tmp_path,
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: integer",
            ]
        ),
    )

    with pytest.raises(ValidationError) as exc:
        schema_module.load_schema(path)

    assert isinstance(exc.value.__cause__, PydanticValidationError)


def test_schema_validation_failure_includes_failure_details(tmp_path):
    pytest.importorskip("pandera")
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
    df = pd.DataFrame({"age": [200]})

    schema = schema_module.load_schema(schema_path)
    with pytest.raises(ValidationError) as exc:
        schema_module.validate_df(df, schema)

    message = str(exc.value)
    assert message.startswith("Schema validation failed:")
    assert "age" in message


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

    original_import = schema_module.importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "pandera":
            raise ImportError("pandera missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(schema_module.importlib, "import_module", fake_import)

    with pytest.raises(DependencyError) as exc:
        schema_module.load_schema(path)

    assert "cleanmydata[schema]" in str(exc.value)
