"""Prompt templates for Gemini data quality suggestions."""

from __future__ import annotations

import json


def build_quality_prompt(payload: dict) -> str:
    """
    Build a strict, JSON-only prompt for Gemini data quality suggestions.

    Requirements enforced in prompt:
    - Advisory only (no data mutation, no actions).
    - Use only provided schema/summary/sample; never request more data.
    - Return STRICT JSON only (no markdown, no prose).
    - Output must follow the exact schema below.
    """

    schema = """
Return EXACTLY one JSON object matching this schema (no markdown, no prose):
{
  "suggestions": [
    {
      "category": "schema|quality|missing|duplicates|outliers|formatting|business_rules",
      "severity": "info|warning|critical",
      "message": "short actionable text",
      "column": "optional column name or null",
      "evidence": { "optional": "small supporting fields" }
    }
  ]
}
Rules:
- suggestions must be an array (can be empty)
- max 12 suggestions
- messages must be concise and specific
- evidence must be small (no row dumps, no PII)
- do not include job_id, file paths, or user identifiers
- never request the full dataset
- output must be valid JSON ONLY (no code fences, no extra text)
"""

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    prompt = (
        "You are a data quality advisor. Provide concise, actionable suggestions.\n"
        "You MUST return only valid JSON following the provided schema.\n"
        "Do not mutate data. Do not ask for more data. Do not include markdown or prose.\n"
        f"{schema}\n"
        "DATA (use only this information):\n"
        f"{payload_json}\n"
        "Return ONLY the JSON object, nothing else."
    )

    return prompt
