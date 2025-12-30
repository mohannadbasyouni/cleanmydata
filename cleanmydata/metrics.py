"""Metrics abstraction for Datadog-compatible emission.

Supports DogStatsD when an agent is available, HTTP Metrics API as a fallback,
and a no-op client when neither is configured. All emission is best-effort and
swallows errors to keep the cleaning pipeline resilient.
"""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterable, Sequence
from urllib import request

from cleanmydata.logging import get_logger

logger = get_logger(__name__)

TagList = Sequence[str] | None


class MetricsClient:
    """Interface for emitting metrics."""

    def count(self, name: str, value: float = 1, tags: TagList = None) -> None:  # noqa: B027
        raise NotImplementedError

    def gauge(self, name: str, value: float, tags: TagList = None) -> None:  # noqa: B027
        raise NotImplementedError

    def histogram(self, name: str, value: float, tags: TagList = None) -> None:  # noqa: B027
        raise NotImplementedError


class NoOpMetricsClient(MetricsClient):
    """Swallow all metrics calls."""

    def count(self, name: str, value: float = 1, tags: TagList = None) -> None:  # noqa: ARG002
        return None

    def gauge(self, name: str, value: float, tags: TagList = None) -> None:  # noqa: ARG002
        return None

    def histogram(self, name: str, value: float, tags: TagList = None) -> None:  # noqa: ARG002
        return None


class DogStatsdMetricsClient(MetricsClient):
    """Lightweight DogStatsD UDP client."""

    def __init__(self, host: str, port: int = 8125) -> None:
        self.address = (host, port)

    def _send(self, name: str, value: float, metric_type: str, tags: Iterable[str] | None) -> None:
        try:
            tag_str = ""
            if tags:
                tag_str = f"|#{','.join(tags)}"
            message = f"{name}:{value}|{metric_type}{tag_str}"
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(message.encode("utf-8"), self.address)
        except Exception as exc:  # pragma: no cover - best-effort
            logger.debug("dogstatsd_emit_failed", error=str(exc))

    def count(self, name: str, value: float = 1, tags: TagList = None) -> None:
        self._send(name, value, "c", tags)

    def gauge(self, name: str, value: float, tags: TagList = None) -> None:
        self._send(name, value, "g", tags)

    def histogram(self, name: str, value: float, tags: TagList = None) -> None:
        self._send(name, value, "h", tags)


class HttpMetricsClient(MetricsClient):
    """HTTP fallback using Datadog Metrics API."""

    def __init__(self, api_key: str, site: str, timeout: float = 2.0) -> None:
        self.api_key = api_key
        self.site = site
        self.timeout = timeout
        self.endpoint = f"https://api.{site}/api/v2/series"

    def _send(
        self,
        name: str,
        value: float,
        metric_type: str,
        tags: Iterable[str] | None,
    ) -> None:
        try:
            payload = {
                "series": [
                    {
                        "metric": name,
                        "points": [[int(time.time()), float(value)]],
                        "type": metric_type,
                        "tags": list(tags) if tags else [],
                    }
                ]
            }
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                self.endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "DD-API-KEY": self.api_key,
                },
                method="POST",
            )
            with request.urlopen(req, timeout=self.timeout):
                pass
        except Exception as exc:  # pragma: no cover - best-effort
            logger.debug("http_metrics_emit_failed", error=str(exc))

    def count(self, name: str, value: float = 1, tags: TagList = None) -> None:
        self._send(name, value, "count", tags)

    def gauge(self, name: str, value: float, tags: TagList = None) -> None:
        self._send(name, value, "gauge", tags)

    def histogram(self, name: str, value: float, tags: TagList = None) -> None:
        # Datadog treats histograms over HTTP as distributions.
        self._send(name, value, "distribution", tags)


def get_metrics_client() -> MetricsClient:
    """
    Return an appropriate MetricsClient based on environment variables.

    Preference order:
        1. DogStatsD if DD_AGENT_HOST is set.
        2. HTTP Metrics API if DD_API_KEY and DD_SITE are set.
        3. No-op client otherwise.
    """
    agent_host = os.getenv("DD_AGENT_HOST")
    if agent_host:
        port = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))
        return DogStatsdMetricsClient(agent_host, port)

    api_key = os.getenv("DD_API_KEY")
    site = os.getenv("DD_SITE")
    if api_key and site:
        return HttpMetricsClient(api_key=api_key, site=site)

    return NoOpMetricsClient()


def default_metric_tags() -> list[str]:
    """
    Return default metric tags for all metrics.

    Includes:
    - service:cleanmydata-api (standardized service tag)
    - env:<value> (if DD_ENV or CLEANMYDATA_ENV is set, otherwise omitted)

    Returns:
        List of tag strings in the format "key:value".
    """
    tags = ["service:cleanmydata-api"]
    env_value = os.getenv("DD_ENV") or os.getenv("CLEANMYDATA_ENV")
    if env_value:
        tags.append(f"env:{env_value}")
    return tags
