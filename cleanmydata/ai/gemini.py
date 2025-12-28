"""Vertex AI Gemini client for advisory data-quality analysis."""

from __future__ import annotations

import os
import time
from contextlib import nullcontext
from typing import Any

import pandas as pd

from cleanmydata.ai.prompts import build_quality_prompt
from cleanmydata.logging import get_logger
from cleanmydata.models import Suggestion

try:  # pragma: no cover - optional dependency
    from ddtrace import tracer  # type: ignore
except Exception:  # pragma: no cover - fallback when ddtrace missing
    tracer = None

logger = get_logger(__name__)


def _env_truthy(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


class GeminiClient:
    """Lightweight, advisory-only Gemini client."""

    def __init__(self) -> None:
        self.enabled = _env_truthy(os.getenv("CLEANMYDATA_GEMINI_ENABLED"))
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
        self.model = os.getenv("CLEANMYDATA_GEMINI_MODEL") or "gemini-1.5-flash-002"

    def analyze_data_quality(
        self, df: pd.DataFrame, summary: dict[str, Any], *, dataset_kind: str | None = None
    ) -> list[Suggestion]:
        """
        Analyze cleaned data and return advisory suggestions.

        Never mutates the dataframe. If Gemini is disabled or misconfigured,
        returns an empty list and logs at debug level.
        """

        start = time.perf_counter()

        if not self.enabled:
            logger.debug("gemini_disabled")
            return []

        if not self.project:
            logger.debug("gemini_missing_project", enabled=self.enabled)
            return []

        span_ctx = (
            tracer.trace("cleanmydata.ai.gemini_analyze", service="cleanmydata")
            if tracer
            else nullcontext()
        )

        with span_ctx as span:
            if span and span is not None:
                span.set_tag("dataset_kind", dataset_kind or "unknown")
                span.set_tag("rows", summary.get("rows", len(df)))
                span.set_tag("columns", summary.get("columns", len(df.columns)))
                span.set_tag("model", self.model)

            logger.info(
                "gemini_analysis_started",
                dataset_kind=dataset_kind,
                rows=summary.get("rows", len(df)),
                columns=summary.get("columns", len(df.columns)),
                model=self.model,
            )

            try:
                payload = self._build_payload(df, summary, dataset_kind)
                raw_response = self._invoke_model(payload)
                suggestions = self._parse_suggestions(raw_response)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "gemini_analysis_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    dataset_kind=dataset_kind,
                    model=self.model,
                    exc_info=True,
                )
                return []
            finally:
                duration_ms = int((time.perf_counter() - start) * 1000)
                suggestions_count = len(locals().get("suggestions", []))
                logger.info(
                    "gemini_analysis_completed",
                    duration_ms=duration_ms,
                    suggestions_count=suggestions_count,
                    model=self.model,
                )
                if span and span is not None:
                    span.set_tag("duration_ms", duration_ms)
                    span.set_tag("suggestions_count", suggestions_count)

        return suggestions

    def _build_payload(
        self, df: pd.DataFrame, summary: dict[str, Any], dataset_kind: str | None
    ) -> dict[str, Any]:
        sample_df = df.head(50).copy()
        sample_records = sample_df.to_dict(orient="records")

        def _truncate(value: Any, max_len: int = 200) -> Any:
            if value is None:
                return None
            if isinstance(value, float) and pd.isna(value):
                return None
            text = str(value)
            return text[:max_len]

        safe_sample = [{k: _truncate(v) for k, v in row.items()} for row in sample_records]

        schema = [{"name": col, "dtype": str(dtype)} for col, dtype in df.dtypes.items()]

        missing_pct = {col: float(df[col].isna().mean() * 100) for col in df.columns}

        small_cardinality = {}
        for col in df.columns:
            unique_count = int(df[col].nunique(dropna=True))
            if unique_count <= 50:
                small_cardinality[col] = unique_count

        numeric_stats = {}
        numeric_cols = df.select_dtypes(include=["number"]).columns
        for col in numeric_cols:
            series = df[col]
            numeric_stats[col] = {
                "mean": float(series.mean(skipna=True)),
                "std": float(series.std(skipna=True)),
                "min": float(series.min(skipna=True)),
                "max": float(series.max(skipna=True)),
                "median": float(series.median(skipna=True)),
            }

        payload = {
            "context": "You are a data quality advisor. Respond with JSON only.",
            "dataset_kind": dataset_kind or "unknown",
            "summary": summary,
            "schema": schema,
            "missing_pct": missing_pct,
            "small_cardinality": small_cardinality,
            "numeric_stats": numeric_stats,
            "sample_rows": safe_sample,
            "instructions": {
                "output_schema": {
                    "suggestions": [
                        {
                            "category": "schema|quality|missing|duplicates|outliers|formatting|business_rules",
                            "severity": "info|warning|critical",
                            "message": "short actionable text",
                            "column": "optional column name or null",
                            "evidence": {"optional": "small supporting fields"},
                        }
                    ]
                },
                "rules": [
                    "Do not include dataset values beyond provided sample.",
                    "Do not invent columns.",
                    "Prefer concise, actionable suggestions.",
                    'Return a single JSON object: {"suggestions":[...]}',
                    "Max 12 suggestions.",
                    "No markdown, no code fences, no extra text.",
                ],
            },
        }

        return payload

    def _invoke_model(self, payload: dict[str, Any]) -> str | list[Any] | dict[str, Any]:
        """Call Vertex AI Gemini. Separated for easy mocking in tests."""
        try:
            from vertexai import init as vertexai_init  # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.debug("gemini_dependency_missing", error=str(exc))
            return ""

        vertexai_init(project=self.project, location=self.location)
        model = GenerativeModel(self.model)

        prompt = build_quality_prompt(payload)

        response = model.generate_content(
            [prompt],
            generation_config={"response_mime_type": "application/json"},
        )

        text = getattr(response, "text", None)
        if not text and getattr(response, "candidates", None):
            parts = response.candidates[0].content.parts
            text = "".join([getattr(p, "text", "") for p in parts])

        return text or ""

    def _parse_suggestions(self, raw: str | list[Any] | dict[str, Any]) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        allowed_categories = {
            "schema",
            "quality",
            "missing",
            "duplicates",
            "outliers",
            "formatting",
            "business_rules",
        }
        allowed_severities = {"info", "warning", "critical"}

        def _coerce_entry(item: dict[str, Any]) -> Suggestion | None:
            category = str(item.get("category", "quality")).lower()
            severity = str(item.get("severity", "info")).lower()
            if category not in allowed_categories:
                category = "quality"
            if severity not in allowed_severities:
                severity = "info"
            message = str(item.get("message", "")).strip()
            if not message:
                return None
            column_val = item.get("column")
            if isinstance(column_val, str) and not column_val.strip():
                column_val = None
            evidence_val = item.get("evidence")
            if evidence_val is not None and not isinstance(evidence_val, dict):
                evidence_val = None
            return Suggestion(
                category=category,
                severity=severity,
                message=message,
                column=column_val,
                evidence=evidence_val,
            )

        structured: list[Any] | None = None

        if isinstance(raw, list):
            structured = raw
        elif isinstance(raw, dict):
            structured = (
                raw.get("suggestions") if isinstance(raw.get("suggestions"), list) else None
            )
        elif isinstance(raw, str):
            text = raw.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines and lines[0].lstrip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            try:
                import json  # local import to avoid module import when unused

                parsed = json.loads(text)
                if isinstance(parsed, dict) and "suggestions" in parsed:
                    structured = parsed.get("suggestions")
                elif isinstance(parsed, list):
                    structured = parsed
            except Exception as exc:
                logger.error(
                    "gemini_parse_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return []

        if not structured:
            return []

        for item in structured[:12]:
            if not isinstance(item, dict):
                continue
            coerced = _coerce_entry(item)
            if coerced:
                suggestions.append(coerced)
        return suggestions
