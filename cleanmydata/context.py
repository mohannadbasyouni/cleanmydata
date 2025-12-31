from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
