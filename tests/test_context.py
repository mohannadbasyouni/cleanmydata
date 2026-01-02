from __future__ import annotations

import os
import subprocess
import sys

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


def test_context_importable_without_rich_subprocess() -> None:
    script = r"""
import importlib.abc
import sys


class _BlockRich(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "rich" or fullname.startswith("rich."):
            raise ModuleNotFoundError("No module named 'rich'")
        return None


sys.meta_path.insert(0, _BlockRich())
import cleanmydata.context as ctx

assert isinstance(ctx.map_exception_to_exit_code(Exception("boom")), int)
"""
    env = os.environ.copy()
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("DD_TRACE_ENABLED", "false")
    env.setdefault("DD_TRACE_STARTUP_LOGS", "false")

    subprocess.run([sys.executable, "-c", script], check=True, env=env)
