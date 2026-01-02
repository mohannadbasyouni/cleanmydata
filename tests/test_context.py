from __future__ import annotations

from cleanmydata.constants import EXIT_GENERAL_ERROR, EXIT_INVALID_INPUT, EXIT_IO_ERROR
from cleanmydata.context import map_exception_to_exit_code
from cleanmydata.exceptions import (
    CleanIOError,
    DataLoadError,
    DependencyError,
    InvalidInputError,
    ValidationError,
)


def test_map_exception_to_exit_code_file_not_found_error() -> None:
    assert map_exception_to_exit_code(FileNotFoundError("missing")) == EXIT_IO_ERROR


def test_map_exception_to_exit_code_data_load_error() -> None:
    assert map_exception_to_exit_code(DataLoadError("load failed")) == EXIT_IO_ERROR


def test_map_exception_to_exit_code_clean_io_error() -> None:
    assert map_exception_to_exit_code(CleanIOError("io failed")) == EXIT_IO_ERROR


def test_map_exception_to_exit_code_validation_error() -> None:
    assert map_exception_to_exit_code(ValidationError("invalid config")) == EXIT_INVALID_INPUT


def test_map_exception_to_exit_code_invalid_input_error() -> None:
    assert map_exception_to_exit_code(InvalidInputError("invalid input")) == EXIT_INVALID_INPUT


def test_map_exception_to_exit_code_dependency_error() -> None:
    assert map_exception_to_exit_code(DependencyError("missing dependency")) == EXIT_INVALID_INPUT


def test_map_exception_to_exit_code_generic_exception() -> None:
    assert map_exception_to_exit_code(Exception("boom")) == EXIT_GENERAL_ERROR
