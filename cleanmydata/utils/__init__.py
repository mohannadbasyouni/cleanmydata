"""Utility functions for cleanmydata."""

import json
import re
from datetime import datetime

try:
    from ddtrace import tracer as dd_tracer
except ImportError:
    dd_tracer = None

RUN_START_RE = re.compile(r"Cleaning Run #\d+ — Started")


def get_trace_context():
    """
    Get current Datadog trace context for log correlation.

    Returns:
        dict: Dictionary containing dd.trace_id, dd.span_id, and dd.service
              Returns empty dict if no active trace.
    """
    context = {}
    if dd_tracer:
        current_span = dd_tracer.current_span()
        if current_span:
            context["dd.trace_id"] = str(current_span.trace_id)
            context["dd.span_id"] = str(current_span.span_id)
            context["dd.service"] = "cleanmydata"
    return context


def log_json(message, level="info", **extra_fields):
    """
    Write a JSON-formatted log entry with Datadog trace correlation.

    Args:
        message: Log message
        level: Log level (info, warning, error, etc.)
        **extra_fields: Additional fields to include in the log entry
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "message": message,
        "service": "cleanmydata",
    }

    # Add trace context if available
    trace_context = get_trace_context()
    log_entry.update(trace_context)

    # Add extra fields
    log_entry.update(extra_fields)

    # Write to stdout as JSON (for Datadog agent to collect)
    print(json.dumps(log_entry))
