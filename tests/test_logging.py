import json
import sys
import types

import pytest

from cleanmydata.logging import configure_logging_json, get_logger, reset_logging_for_tests


@pytest.fixture(autouse=True)
def reset_logging_state():
    reset_logging_for_tests()
    yield
    reset_logging_for_tests()
    sys.modules.pop("ddtrace", None)


def test_logs_are_json_and_have_required_fields(capsys):
    configure_logging_json()
    logger = get_logger("test")

    logger.info("clean_step_completed", step="demo")
    out, err = capsys.readouterr()

    assert err == ""
    record = json.loads(out.strip())
    assert record["event"] == "clean_step_completed"
    assert record["service"] == "cleanmydata"
    assert record["runtime"] == "cloudrun"
    assert record["level"] == "INFO"
    assert "timestamp" in record
    assert record["step"] == "demo"


def test_dd_context_added_when_span_exists(monkeypatch, capsys):
    fake_span = types.SimpleNamespace(trace_id=123, span_id=456)
    fake_tracer = types.SimpleNamespace(current_span=lambda: fake_span)
    monkeypatch.setitem(sys.modules, "ddtrace", types.SimpleNamespace(tracer=fake_tracer))

    configure_logging_json()
    logger = get_logger("test")
    logger.info("clean_request_started")

    out, err = capsys.readouterr()
    assert err == ""
    record = json.loads(out.strip())
    assert record["dd.trace_id"] == "123"
    assert record["dd.span_id"] == "456"


def test_no_dd_fields_without_span(monkeypatch, capsys):
    monkeypatch.delitem(sys.modules, "ddtrace", raising=False)

    configure_logging_json()
    logger = get_logger("test")
    logger.info("clean_request_started")

    out, err = capsys.readouterr()
    assert err == ""
    record = json.loads(out.strip())
    assert "dd.trace_id" not in record
    assert "dd.span_id" not in record


def test_errors_route_to_stderr(capsys):
    configure_logging_json()
    logger = get_logger("test")

    logger.error("clean_request_failed", error_type="ValueError", error_message="boom")
    out, err = capsys.readouterr()

    assert out == ""
    record = json.loads(err.strip())
    assert record["event"] == "clean_request_failed"
    assert record["level"] == "ERROR"
    assert record["error_message"] == "boom"
