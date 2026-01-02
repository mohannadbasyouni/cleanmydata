from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from cleanmydata.config import CleaningConfig


class ConsoleLike(Protocol):
    def print(
        self,
        *objects: object,
        soft_wrap: bool | None = None,
        overflow: Literal["fold", "crop", "ellipsis", "ignore"] | None = None,
        no_wrap: bool | None = None,
    ) -> None: ...

    def rule(
        self,
        title: str,
        *,
        style: str = "rule.line",
    ) -> None: ...


class PlainConsole:
    """
    Minimal fallback for when `rich` isn't installed.

    Supports the subset of the Rich Console API we rely on (`print`, `rule`),
    without styling/markup features.
    """

    def __init__(self, *, stderr: bool = False, **_kwargs: object) -> None:
        self._stderr = stderr

    def print(self, *objects: object, **_kwargs: object) -> None:
        import sys

        stream = sys.stderr if self._stderr else sys.stdout
        print(*objects, file=stream)

    def rule(self, *objects: object, **_kwargs: object) -> None:
        self.print(*objects)


def _make_console(*, stderr: bool) -> ConsoleLike:
    """
    Create a console instance without requiring `rich` at import time.

    When `rich` is available, returns `rich.console.Console` configured exactly
    as before. Otherwise returns a minimal `PlainConsole`.
    """
    try:
        from rich.console import Console as RichConsole
    except ModuleNotFoundError:
        return PlainConsole(stderr=stderr)

    return RichConsole(
        stderr=stderr,
        force_terminal=False,
        color_system=None,
        markup=False,
        highlight=False,
        width=4000,
    )


@dataclass
class AppContext:
    """
    CLI execution context. Created once at CLI entry point.
    Core functions do not create or depend on this.
    """

    mode: Literal["normal", "quiet", "silent"]
    verbose: bool
    log_to_file: bool
    config: CleaningConfig
    _console: ConsoleLike | None = field(default=None, init=False, repr=False)
    _stderr_console: ConsoleLike | None = field(default=None, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        quiet: bool = False,
        silent: bool = False,
        verbose: bool = False,
        log_to_file: bool = False,
        config: CleaningConfig | None = None,
    ) -> AppContext:
        """
        Factory method to create AppContext.
        Silent overrides quiet.
        """
        if silent:
            mode = "silent"
        elif quiet:
            mode = "quiet"
        else:
            mode = "normal"

        return cls(
            mode=mode,
            verbose=verbose,
            log_to_file=log_to_file,
            config=config or CleaningConfig(),
        )

    def get_console(self, *, stderr: bool = False) -> ConsoleLike:
        """
        Return a cached console configured for stdout or stderr.
        """

        if stderr:
            if self._stderr_console is None:
                self._stderr_console = _make_console(stderr=True)
            return self._stderr_console

        if self._console is None:
            self._console = _make_console(stderr=False)
        return self._console

    @property
    def quiet_mode(self) -> bool:
        """
        True when stdout should be suppressed (except required outputs).
        """
        return self.mode in {"quiet", "silent"}

    @property
    def silent_mode(self) -> bool:
        """
        True when all stdout output should be suppressed.
        """
        return self.mode == "silent"


def map_exception_to_exit_code(exc: Exception) -> int:
    """
    Map exceptions to CLI exit codes.
    Centralized mapping for consistent behavior.
    """
    from cleanmydata.constants import (
        EXIT_GENERAL_ERROR,
        EXIT_INVALID_INPUT,
        EXIT_IO_ERROR,
    )
    from cleanmydata.exceptions import (
        CleanIOError,
        DataLoadError,
        DependencyError,
        InvalidInputError,
        ValidationError,
    )

    if isinstance(exc, FileNotFoundError):
        return EXIT_IO_ERROR
    if isinstance(exc, (DataLoadError, CleanIOError)):
        return EXIT_IO_ERROR
    if isinstance(exc, (ValidationError, InvalidInputError, DependencyError)):
        return EXIT_INVALID_INPUT
    return EXIT_GENERAL_ERROR
