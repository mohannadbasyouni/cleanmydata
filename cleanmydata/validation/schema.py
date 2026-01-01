"""Pandera-backed schema validation helpers."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from cleanmydata.exceptions import DependencyError, ValidationError

AllowedDtype = Literal["int", "float", "str", "bool", "datetime"]


def _require_pandera():
    try:
        return importlib.import_module("pandera")
    except ImportError as exc:
        raise DependencyError(
            'Schema validation is not installed. Install with: pip install "cleanmydata[schema]"'
        ) from exc


class CheckSpec(BaseModel):
    """Supported column checks."""

    model_config = ConfigDict(extra="forbid")

    in_range: dict[str, float] | None = None
    isin: list[Any] | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def _validate_exactly_one(self) -> CheckSpec:
        present = [self.in_range is not None, self.isin is not None, self.regex is not None]
        if sum(present) != 1:
            raise ValueError("exactly one check must be provided (in_range, isin, or regex)")

        if self.in_range is not None:
            keys = set(self.in_range.keys())
            if not {"min", "max"}.issubset(keys):
                raise ValueError("in_range must include min and max")
        return self

    def to_pandera(self, pa) -> Any:
        if self.in_range is not None:
            return pa.Check.in_range(self.in_range["min"], self.in_range["max"])
        if self.isin is not None:
            return pa.Check.isin(self.isin)
        if self.regex is not None:
            return pa.Check.str_matches(self.regex)
        raise ValueError("Unsupported check")


class ColumnSpec(BaseModel):
    """Column definition."""

    model_config = ConfigDict(extra="forbid")

    dtype: AllowedDtype
    nullable: bool = False
    required: bool = True
    checks: list[CheckSpec] | None = None

    @model_validator(mode="after")
    def _validate_checks(self) -> ColumnSpec:
        if not self.checks:
            return self

        for check in self.checks:
            if check.regex is not None and self.dtype != "str":
                raise ValueError("regex check is only supported for dtype=str")
            if check.in_range is not None and self.dtype not in {"int", "float"}:
                raise ValueError("in_range check is only supported for numeric dtypes")
        return self


class SchemaSpec(BaseModel):
    """Top-level schema specification."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    columns: dict[str, ColumnSpec] = Field(..., description="Column specifications")


def _dtype_to_pandera(pa, dtype: AllowedDtype):
    mapping = {
        "int": pa.Int64,
        "float": pa.Float64,
        "str": pa.String,
        "bool": pa.Bool,
        "datetime": pa.DateTime,
    }
    return mapping[dtype]


def _build_schema(pa, spec: SchemaSpec):
    columns = {}
    for col_name, col_spec in spec.columns.items():
        checks = [chk.to_pandera(pa) for chk in col_spec.checks or []]
        columns[col_name] = pa.Column(
            _dtype_to_pandera(pa, col_spec.dtype),
            nullable=col_spec.nullable,
            required=col_spec.required,
            checks=checks or None,
        )

    return pa.DataFrameSchema(columns, coerce=True)


def load_schema(path: Path):
    """Load a DataFrame schema from YAML into a pandera.DataFrameSchema."""

    pa = _require_pandera()
    schema_path = Path(path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    try:
        with schema_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in schema file: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError("Schema file must contain a top-level mapping")

    try:
        spec = SchemaSpec(**data)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc)) from exc

    return _build_schema(pa, spec)


def _summarize_failures(failures: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    for failure in failures:
        col = failure.get("column", "<unknown>")
        check = failure.get("check", "<check>")
        case = failure.get("failure_case", "<failure>")
        parts.append(f"{col}: {check} ({case})")
    return "; ".join(parts)


def validate_df(df: pd.DataFrame, schema) -> None:
    """Validate a DataFrame against a pandera schema."""

    pa = _require_pandera()
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        failures = exc.failure_cases.head(3).to_dict("records")
        message = _summarize_failures(failures)
        raise ValidationError(f"Schema validation failed: {message}") from exc
    except pa.errors.SchemaError as exc:
        raise ValidationError(f"Schema validation failed: {exc}") from exc


def validate_df_with_yaml(df: pd.DataFrame, schema_path: Path) -> None:
    """Load a YAML schema and validate a DataFrame."""

    schema = load_schema(schema_path)
    validate_df(df, schema)
