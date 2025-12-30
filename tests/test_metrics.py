from pathlib import Path

import pandas as pd
import pytest

from cleanmydata.clean import clean_data
from cleanmydata.metrics import MetricsClient, NoOpMetricsClient, get_metrics_client
from cleanmydata.utils.io import read_data


class RecordingMetrics(MetricsClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float, list[str]]] = []

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


class RaisingMetrics(MetricsClient):
    def count(self, name: str, value: float = 1, tags=None) -> None:  # noqa: ARG002
        raise RuntimeError("metrics error")

    def gauge(self, name: str, value: float, tags=None) -> None:  # noqa: ARG002
        raise RuntimeError("metrics error")

    def histogram(self, name: str, value: float, tags=None) -> None:  # noqa: ARG002
        raise RuntimeError("metrics error")


def test_get_metrics_client_no_env(monkeypatch):
    monkeypatch.delenv("DD_AGENT_HOST", raising=False)
    monkeypatch.delenv("DD_API_KEY", raising=False)
    monkeypatch.delenv("DD_SITE", raising=False)

    client = get_metrics_client()

    assert isinstance(client, NoOpMetricsClient)


def test_clean_data_emits_success_metrics(monkeypatch):
    monkeypatch.setenv("DD_ENV", "test")
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)
    metrics = RecordingMetrics()

    cleaned_df, summary = clean_data(
        df,
        verbose=False,
        metrics_client=metrics,
        dataset_name="small.csv",
    )

    assert not cleaned_df.empty
    assert summary["rows"] == cleaned_df.shape[0]
    total_call = metrics.find("count", "cleanmydata.requests_total")
    success_call = metrics.find("count", "cleanmydata.requests_succeeded_total")
    histogram_call = metrics.find("histogram", "cleanmydata.duration_ms")

    assert total_call is not None
    assert success_call is not None
    assert histogram_call is not None
    for tag in ("service:cleanmydata-api", "env:test", "runtime:cloudrun"):
        assert tag in total_call[3]
    assert "dataset_kind:csv" in total_call[3]
    assert "outliers_method:cap" in total_call[3]
    assert "excel_used:false" in total_call[3]
    assert "status:success" in success_call[3]
    assert histogram_call[2] > 0


def test_clean_data_emits_failure_metrics(monkeypatch):
    monkeypatch.setenv("DD_ENV", "test")
    df = pd.DataFrame({"a": [1, 2, 3]})
    metrics = RecordingMetrics()

    def boom(*args, **kwargs):  # noqa: ARG001
        raise ValueError("boom")

    monkeypatch.setattr("cleanmydata.clean.remove_duplicates", boom)

    with pytest.raises(ValueError):
        clean_data(df, verbose=False, metrics_client=metrics, dataset_name="fail.csv")

    total_call = metrics.find("count", "cleanmydata.requests_total")
    failed_call = metrics.find("count", "cleanmydata.requests_failed_total")
    histogram_call = metrics.find("histogram", "cleanmydata.duration_ms")

    assert total_call is not None
    assert failed_call is not None
    assert histogram_call is not None
    assert "status:failure" in failed_call[3]


def test_metrics_errors_are_swallowed(monkeypatch):
    monkeypatch.setenv("DD_ENV", "test")
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    df = read_data(fixture_path)

    metrics = RaisingMetrics()
    cleaned_df, summary = clean_data(
        df,
        verbose=False,
        metrics_client=metrics,
        dataset_name="small.csv",
    )

    assert not cleaned_df.empty
    assert summary["rows"] == cleaned_df.shape[0]
