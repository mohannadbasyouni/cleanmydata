"""Vertex AI Gemini client for advisory data-quality analysis."""

from __future__ import annotations

import json
import os
import time
from contextlib import nullcontext
from typing import Any

import pandas as pd

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
                raw_suggestions = self._invoke_model(payload)
                suggestions = self._parse_suggestions(raw_suggestions)
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
                logger.info(
                    "gemini_analysis_completed",
                    duration_ms=duration_ms,
                    suggestions=len(locals().get("suggestions", [])),
                    model=self.model,
                )
                if span and span is not None:
                    span.set_tag("duration_ms", duration_ms)
                    span.set_tag("suggestions", len(locals().get("suggestions", [])))

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
                "output_format": {
                    "category": "schema|quality|outliers|formatting|duplicates|missing|business_rules",
                    "severity": "info|warning|critical",
                    "message": "short human-friendly message",
                    "column": "optional column name",
                    "evidence": "optional dict with supporting facts",
                },
                "rules": [
                    "Do not include dataset values beyond provided sample.",
                    "Do not invent columns.",
                    "Prefer concise, actionable suggestions.",
                    "Return a JSON list of suggestions.",
                ],
            },
        }

        return payload

    def _invoke_model(self, payload: dict[str, Any]) -> list[Any]:
        """Call Vertex AI Gemini. Separated for easy mocking in tests."""
        try:
            from vertexai import init as vertexai_init  # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.debug("gemini_dependency_missing", error=str(exc))
            return []

        vertexai_init(project=self.project, location=self.location)
        model = GenerativeModel(self.model)

        response = model.generate_content(
            [
                "You are a data quality analyst. Return JSON only as a list of suggestions.",
                json.dumps(payload, ensure_ascii=False),
            ],
            generation_config={"response_mime_type": "application/json"},
        )

        text = getattr(response, "text", None)
        if not text and getattr(response, "candidates", None):
            parts = response.candidates[0].content.parts
            text = "".join([getattr(p, "text", "") for p in parts])

        if not text:
            return []

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("gemini_response_not_json")
            return []

        if isinstance(parsed, dict) and "suggestions" in parsed:
            parsed = parsed["suggestions"]

        return parsed if isinstance(parsed, list) else []

    def _parse_suggestions(self, raw: list[Any]) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            try:
                suggestions.append(
                    Suggestion(
                        category=str(item.get("category", "quality")),
                        severity=str(item.get("severity", "info")),
                        message=str(item.get("message", "")).strip(),
                        column=item.get("column"),
                        evidence=item.get("evidence"),
                    )
                )
            except Exception:
                continue
        return suggestions
