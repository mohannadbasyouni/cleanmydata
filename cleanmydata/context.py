from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.console import Console

from cleanmydata.config import CleaningConfig


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
    _console: Console | None = field(default=None, init=False, repr=False)
    _stderr_console: Console | None = field(default=None, init=False, repr=False)

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

    def get_console(self, *, stderr: bool = False) -> Console:
        """
        Return a cached console configured for stdout or stderr.
        """
        if stderr:
            if self._stderr_console is None:
                self._stderr_console = Console(
                    stderr=True,
                    force_terminal=False,
                    color_system=None,
                    markup=False,
                    highlight=False,
                    width=4000,
                )
            return self._stderr_console

        if self._console is None:
            self._console = Console(
                stderr=False,
                force_terminal=False,
                color_system=None,
                markup=False,
                highlight=False,
                width=4000,
            )
        return self._console


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
