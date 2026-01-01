"""Structured JSON logging configured for Datadog compatibility.

Structured logging emits structured JSON so downstream systems and Datadog
have machine-parseable events, while RichHandler (rich console logging) is
limited to CLI wiring where human-friendly terminal output is desired.
configure_logging_json exists for CLI wiring only; library consumers should
not force a global logging configuration.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from collections.abc import Callable, MutableMapping
from typing import Any

import structlog

JsonDict = MutableMapping[str, Any]


def _env_tag() -> str:
    return os.getenv("CLEANMYDATA_ENV") or os.getenv("ENV") or os.getenv("DD_ENV") or "dev"


def _add_base_fields(service: str, runtime: str) -> Callable[[Any, str, JsonDict], JsonDict]:
    def processor(logger: Any, method_name: str, event_dict: JsonDict) -> JsonDict:  # noqa: ANN401
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", _env_tag())
        event_dict.setdefault("runtime", runtime)
        event_dict.setdefault("event", method_name)
        return event_dict

    return processor


def _add_datadog_context(logger: Any, method_name: str, event_dict: JsonDict) -> JsonDict:  # noqa: ANN401
    try:
        from ddtrace import tracer  # type: ignore
    except Exception:
        return event_dict

    span = tracer.current_span()
    if span:
        event_dict["dd.trace_id"] = str(getattr(span, "trace_id", ""))
        event_dict["dd.span_id"] = str(getattr(span, "span_id", ""))
    return event_dict


def _format_exception(logger: Any, method_name: str, event_dict: JsonDict) -> JsonDict:  # noqa: ANN401
    exc_info = event_dict.pop("exc_info", None)
    if not exc_info:
        return event_dict

    if exc_info is True:
        exc_info = sys.exc_info()

    if exc_info and exc_info[0]:
        event_dict["error_type"] = getattr(exc_info[0], "__name__", str(exc_info[0]))
        event_dict["error_message"] = str(exc_info[1])
        event_dict["stack_trace"] = "".join(traceback.format_exception(*exc_info))
    return event_dict


def _finalize_event_factory(
    service: str, runtime: str, timestamper: Callable[[Any, str, JsonDict], JsonDict]
) -> Callable[[Any, str, JsonDict], str]:
    def _finalize_event(logger: Any, method_name: str, event_dict: JsonDict) -> str:  # noqa: ANN401
        event_dict = timestamper(logger, method_name, event_dict)
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", _env_tag())
        event_dict.setdefault("runtime", runtime)
        event_dict = _add_datadog_context(logger, method_name, event_dict)
        event_dict = _format_exception(logger, method_name, event_dict)
        event_dict["level"] = str(event_dict.get("level", method_name)).upper()
        event_dict.setdefault("event", method_name)
        return json.dumps(event_dict, ensure_ascii=True, separators=(",", ":"))

    return _finalize_event


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int) -> None:
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        return record.levelno <= self.max_level


def configure_logging_json(
    level: str = "INFO", service: str = "cleanmydata", runtime: str = "cloudrun"
) -> None:
    """
    Configure structlog to emit JSON logs to stdout/stderr.

    This should be called only at process boundaries (CLI or API startup).
    """

    logging_level = logging.getLevelName(level.upper()) if isinstance(level, str) else level

    timestamper = structlog.processors.TimeStamper(fmt="iso", key="timestamp")
    base_fields = _add_base_fields(service=service, runtime=runtime)
    finalize = _finalize_event_factory(service=service, runtime=runtime, timestamper=timestamper)

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=finalize,
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            timestamper,
            base_fields,
        ],
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging_level)
    stdout_handler.addFilter(_MaxLevelFilter(logging.ERROR - 1))
    stdout_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging_level,
        handlers=[stdout_handler, stderr_handler],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger without configuring global handlers."""

    return structlog.get_logger(name or "cleanmydata")


def reset_logging_for_tests() -> None:
    """Reset structlog and stdlib logging state (used in tests)."""

    structlog.reset_defaults()
    logging.basicConfig(level=logging.NOTSET, handlers=[], force=True)
