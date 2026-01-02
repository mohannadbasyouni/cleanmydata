"""Optional, lightweight profiling utilities (stdlib-only).

Profiling is opt-in. Callers pass a dict "store" to collect timings (in ms).
When profiling is disabled, callers should pass store=None, making this a no-op.

This module intentionally has:
- no external dependencies
- no logging / no printing
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from time import perf_counter


class _NoOpSection(AbstractContextManager[None]):
    def __enter__(self) -> None:  # noqa: D401
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


_NOOP_SECTION = _NoOpSection()


class _ProfileSection(AbstractContextManager[None]):
    def __init__(self, name: str, store: dict[str, float]) -> None:
        self._name = name
        self._store = store
        self._start: float | None = None

    def __enter__(self) -> None:
        self._start = perf_counter()
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._start is None:
            return None
        self._store[self._name] = (perf_counter() - self._start) * 1000.0
        return None


def profile_section(name: str, store: dict[str, float] | None) -> AbstractContextManager[None]:
    """Context manager that records elapsed time into store[name] (ms)."""
    if store is None:
        return _NOOP_SECTION
    return _ProfileSection(name, store)
