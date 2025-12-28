import pandas as pd

from cleanmydata.ai.gemini import GeminiClient
from cleanmydata.ai.prompts import build_quality_prompt
from cleanmydata.models import Suggestion


class RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def debug(self, event: str, **kwargs) -> None:  # noqa: ARG002
        self.events.append(("debug", event))

    def info(self, event: str, **kwargs) -> None:  # noqa: ARG002
        self.events.append(("info", event))

    def error(self, event: str, **kwargs) -> None:  # noqa: ARG002
        self.events.append(("error", event))


def _fresh_df() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def test_gemini_disabled_returns_empty(monkeypatch):
    monkeypatch.delenv("CLEANMYDATA_GEMINI_ENABLED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setattr("cleanmydata.ai.gemini.logger", RecordingLogger())

    client = GeminiClient()
    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2})

    assert suggestions == []
    assert df.equals(_fresh_df())


def test_gemini_missing_project_logs_and_returns_empty(monkeypatch):
    monkeypatch.setenv("CLEANMYDATA_GEMINI_ENABLED", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    recorder = RecordingLogger()
    monkeypatch.setattr("cleanmydata.ai.gemini.logger", recorder)

    client = GeminiClient()
    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2})

    assert suggestions == []
    assert ("debug", "gemini_missing_project") in recorder.events
    assert df.equals(_fresh_df())


def test_gemini_returns_parsed_suggestions(monkeypatch):
    monkeypatch.setenv("CLEANMYDATA_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo")
    recorder = RecordingLogger()
    monkeypatch.setattr("cleanmydata.ai.gemini.logger", recorder)

    client = GeminiClient()
    monkeypatch.setattr(
        client,
        "_invoke_model",
        lambda payload: [
            {
                "category": "quality",
                "severity": "warning",
                "message": "Check column a for zeros",
                "column": "a",
                "evidence": {"zeros": 1},
            }
        ],
    )

    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2}, dataset_kind="csv")

    assert len(suggestions) == 1
    assert isinstance(suggestions[0], Suggestion)
    assert suggestions[0].category == "quality"
    assert suggestions[0].severity == "warning"
    assert suggestions[0].column == "a"
    assert ("info", "gemini_analysis_completed") in recorder.events
    assert df.equals(_fresh_df())


def test_prompt_includes_schema_and_json_requirements():
    payload = {
        "schema": [{"name": "a", "dtype": "int64"}],
        "summary": {"rows": 2, "columns": 1},
        "sample_rows": [{"a": 1}],
    }
    prompt = build_quality_prompt(payload)
    assert "STRICT JSON" in prompt or "JSON ONLY" in prompt.upper()
    assert "max 12 suggestions" in prompt
    assert '"name": "a"' in prompt
    assert '"dtype": "int64"' in prompt


def test_parse_valid_json_object(monkeypatch):
    client = GeminiClient()
    json_text = """
    {
      "suggestions": [
        {
          "category": "schema",
          "severity": "critical",
          "message": "Ensure primary key uniqueness",
          "column": "id",
          "evidence": {"duplicates": 10}
        }
      ]
    }
    """
    suggestions = client._parse_suggestions(json_text)
    assert len(suggestions) == 1
    assert suggestions[0].category == "schema"
    assert suggestions[0].severity == "critical"
    assert suggestions[0].column == "id"


def test_parse_strips_code_fences(monkeypatch):
    client = GeminiClient()
    fenced = """```json
    {"suggestions":[{"category":"quality","severity":"info","message":"trim spaces","column":null}]}
    ```"""
    suggestions = client._parse_suggestions(fenced)
    assert len(suggestions) == 1
    assert suggestions[0].message == "trim spaces"


def test_parse_invalid_json_logs_and_returns_empty(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr("cleanmydata.ai.gemini.logger", recorder)
    client = GeminiClient()
    bad_text = "{not valid json"
    suggestions = client._parse_suggestions(bad_text)
    assert suggestions == []
    assert ("error", "gemini_parse_failed") in recorder.events
