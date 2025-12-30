import pandas as pd

from cleanmydata.ai.gemini import GeminiClient
from cleanmydata.ai.prompts import build_quality_prompt
from cleanmydata.metrics import MetricsClient
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


class RecordingMetrics(MetricsClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float, list[str] | None]] = []

    def count(self, name: str, value: float = 1, tags=None) -> None:  # noqa: ARG002
        self.calls.append(("count", name, value, tags or []))

    def gauge(self, name: str, value: float, tags=None) -> None:  # noqa: ARG002
        self.calls.append(("gauge", name, value, tags or []))

    def histogram(self, name: str, value: float, tags=None) -> None:  # noqa: ARG002
        self.calls.append(("histogram", name, value, tags or []))

    def find(self, metric_type: str, name: str) -> tuple[str, str, float, list[str]] | None:
        for call in self.calls:
            if call[0] == metric_type and call[1] == name:
                return call
        return None


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


def test_gemini_emits_latency_metric(monkeypatch):
    """Test that Gemini analysis emits latency histogram metric."""
    monkeypatch.setenv("CLEANMYDATA_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo")
    metrics = RecordingMetrics()
    monkeypatch.setattr("cleanmydata.ai.gemini.get_metrics_client", lambda: metrics)

    client = GeminiClient()
    monkeypatch.setattr(
        client,
        "_invoke_model",
        lambda payload: [
            {
                "category": "quality",
                "severity": "info",
                "message": "Test suggestion",
            }
        ],
    )

    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2}, dataset_kind="csv")

    assert len(suggestions) == 1
    latency_call = metrics.find("histogram", "cleanmydata.gemini.latency_ms")
    assert latency_call is not None
    assert latency_call[2] >= 0  # duration_ms >= 0
    assert "service:cleanmydata-api" in latency_call[3]
    assert "dataset_kind:csv" in latency_call[3]
    assert "model:" in " ".join(latency_call[3])


def test_gemini_emits_suggestions_count_metric(monkeypatch):
    """Test that Gemini analysis emits suggestions count metric."""
    monkeypatch.setenv("CLEANMYDATA_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo")
    metrics = RecordingMetrics()
    monkeypatch.setattr("cleanmydata.ai.gemini.get_metrics_client", lambda: metrics)

    client = GeminiClient()
    monkeypatch.setattr(
        client,
        "_invoke_model",
        lambda payload: [
            {
                "category": "quality",
                "severity": "info",
                "message": "Suggestion 1",
            },
            {
                "category": "schema",
                "severity": "warning",
                "message": "Suggestion 2",
            },
            {
                "category": "quality",
                "severity": "info",
                "message": "Suggestion 3",
            },
        ],
    )

    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2}, dataset_kind="csv")

    assert len(suggestions) == 3
    # Check total count metric
    total_call = metrics.find("count", "cleanmydata.gemini.suggestions_count")
    assert total_call is not None
    assert total_call[2] == 3.0
    assert "status:success" in total_call[3]
    # Check category-specific counts
    category_calls = [
        call for call in metrics.calls if call[1] == "cleanmydata.gemini.suggestions_count"
    ]
    quality_calls = [c for c in category_calls if "category:quality" in c[3]]
    schema_calls = [c for c in category_calls if "category:schema" in c[3]]
    assert len(quality_calls) > 0
    assert len(schema_calls) > 0


def test_gemini_emits_zero_count_when_disabled(monkeypatch):
    """Test that Gemini emits 0 count metric when disabled."""
    monkeypatch.delenv("CLEANMYDATA_GEMINI_ENABLED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    metrics = RecordingMetrics()
    monkeypatch.setattr("cleanmydata.ai.gemini.get_metrics_client", lambda: metrics)

    client = GeminiClient()
    df = _fresh_df()
    suggestions = client.analyze_data_quality(df, {"rows": 2, "columns": 2})

    assert suggestions == []
    # Should still emit latency metric (0ms)
    latency_call = metrics.find("histogram", "cleanmydata.gemini.latency_ms")
    assert latency_call is not None
    # Should emit skipped count
    skipped_call = metrics.find("count", "cleanmydata.gemini.suggestions_count")
    assert skipped_call is not None
    assert skipped_call[2] == 0.0
    assert "status:skipped" in skipped_call[3]
