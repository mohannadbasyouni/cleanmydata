from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("typer")

from typer.testing import CliRunner

os.environ.setdefault("DD_TRACE_ENABLED", "false")
os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "false")

from cleanmydata.cli import app
from cleanmydata.constants import (
    EXIT_GENERAL_ERROR,
    EXIT_INVALID_INPUT,
    EXIT_IO_ERROR,
    EXIT_SUCCESS,
)
from cleanmydata.context import AppContext, map_exception_to_exit_code
from cleanmydata.exceptions import DependencyError, ValidationError


def _create_sample_csv() -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    tmp.write("name,age\nAlice,30\nBob,31\n")
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def test_appcontext_create_defaults():
    ctx = AppContext.create()
    assert ctx.mode == "normal"
    assert ctx.verbose is False
    assert ctx.log_to_file is False


def test_appcontext_silent_overrides_quiet():
    ctx = AppContext.create(quiet=True, silent=True)
    assert ctx.mode == "silent"


def test_appcontext_quiet_mode():
    ctx = AppContext.create(quiet=True)
    assert ctx.mode == "quiet"


def test_map_exception_file_not_found():
    assert map_exception_to_exit_code(FileNotFoundError()) == EXIT_IO_ERROR


def test_map_exception_validation_error():
    assert map_exception_to_exit_code(ValidationError()) == EXIT_INVALID_INPUT


def test_map_exception_general():
    assert map_exception_to_exit_code(RuntimeError("boom")) == EXIT_GENERAL_ERROR


def test_clean_normal_quiet_silent_flow():
    runner = CliRunner()
    input_path = _create_sample_csv()
    try:
        result = runner.invoke(app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Cleaned data saved as 'out.csv'" in result.stdout
        assert result.stderr == ""

        result_quiet = runner.invoke(app, [str(input_path), "--output", "out.csv", "--quiet"])
        assert result_quiet.exit_code == EXIT_SUCCESS
        assert result_quiet.stdout == "out.csv\n"

        result_silent = runner.invoke(app, [str(input_path), "--output", "out.csv", "--silent"])
        assert result_silent.exit_code == EXIT_SUCCESS
        assert result_silent.stdout == ""
    finally:
        input_path.unlink(missing_ok=True)


def test_cli_filenotfound_exit_code():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["missing.csv", "--output", "out.csv"])
        assert result.exit_code == EXIT_IO_ERROR
        assert "Error loading dataset:" in result.stderr


def test_cli_dataloaderror_exit(monkeypatch):
    from cleanmydata import cli as cli_module
    from cleanmydata.exceptions import DataLoadError

    def boom(*args, **kwargs):
        raise DataLoadError("boom")

    monkeypatch.setattr(cli_module, "read_data", boom)

    runner = CliRunner()
    input_path = _create_sample_csv()
    try:
        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_IO_ERROR
        assert "boom" in result.stderr
    finally:
        input_path.unlink(missing_ok=True)


def test_cli_dependencyerror_exit(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise DependencyError("missing")

    monkeypatch.setattr(cli_module, "read_data", boom)

    runner = CliRunner()
    input_path = _create_sample_csv()
    try:
        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_INVALID_INPUT
    finally:
        input_path.unlink(missing_ok=True)


def test_cli_validationerror_exit(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise ValidationError("bad config")

    monkeypatch.setattr(cli_module, "clean_data", boom)

    runner = CliRunner()
    input_path = _create_sample_csv()
    try:
        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_INVALID_INPUT
    finally:
        input_path.unlink(missing_ok=True)


def test_cli_runtime_error_exit(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "clean_data", boom)

    runner = CliRunner()
    input_path = _create_sample_csv()
    try:
        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_GENERAL_ERROR
    finally:
        input_path.unlink(missing_ok=True)
