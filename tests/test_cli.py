from __future__ import annotations

import os
from pathlib import Path

# Ensure ddtrace doesn't try to emit traces/logging noise during CLI tests.
os.environ.setdefault("DD_TRACE_ENABLED", "false")
os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "false")

from typer.testing import CliRunner

from cleanmydata.cli import app
from cleanmydata.exceptions import DataLoadError, DependencyError, ValidationError


def _write_csv(path: Path) -> None:
    path.write_text("name,age\nAlice,30\nBob,31\n", encoding="utf-8")


def test_clean_normal_writes_info_to_stdout_and_errors_to_stderr_on_success():
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(app, [str(input_path), "--output", "out.csv"])

        assert result.exit_code == 0
        assert "Cleaned data saved as 'out.csv'" in result.stdout
        assert result.stderr == ""
        assert Path("out.csv").exists()


def test_clean_quiet_suppresses_info_but_prints_output_path():
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(app, [str(input_path), "--output", "out.csv", "--quiet"])

        assert result.exit_code == 0
        assert result.stdout == "out.csv\n"
        assert result.stderr == ""
        assert Path("out.csv").exists()


def test_clean_silent_prints_no_stdout_on_success():
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(app, [str(input_path), "--output", "out.csv", "--silent"])

        assert result.exit_code == 0
        assert result.stdout == ""
        assert result.stderr == ""
        assert Path("out.csv").exists()


def test_clean_silent_overrides_quiet():
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(app, [str(input_path), "--output", "out.csv", "--quiet", "--silent"])

        assert result.exit_code == 0
        assert result.stdout == ""
        assert result.stderr == ""
        assert Path("out.csv").exists()


def test_cli_filenotfound_maps_to_exit_io_error_and_writes_error_to_stderr():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["missing.csv", "--output", "out.csv"])

        assert result.exit_code == 3
        assert result.stdout == ""
        assert "Error loading dataset:" in result.stderr


def test_cli_quiet_still_writes_errors_to_stderr_and_no_stdout():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["missing.csv", "--output", "out.csv", "--quiet"])

        assert result.exit_code == 3
        assert result.stdout == ""
        assert "Error loading dataset:" in result.stderr


def test_cli_dataloaderror_maps_to_exit_io_error(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise DataLoadError("boom")

    monkeypatch.setattr(cli_module, "read_data", boom)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli_module.app, ["input.csv", "--output", "out.csv"])

        assert result.exit_code == 3
        assert result.stdout == ""
        assert "Error loading dataset:" in result.stderr
        assert "boom" in result.stderr


def test_cli_dependencyerror_maps_to_exit_invalid_input(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise DependencyError("missing dep")

    monkeypatch.setattr(cli_module, "read_data", boom)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli_module.app, ["input.xlsx", "--output", "out.csv"])

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "Error loading dataset:" in result.stderr
        assert "missing dep" in result.stderr


def test_cli_validationerror_maps_to_exit_invalid_input(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise ValidationError("bad config")

    monkeypatch.setattr(cli_module, "clean_data", boom)

    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "bad config" in result.stderr


def test_cli_unexpected_exception_maps_to_exit_general_error(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "clean_data", boom)

    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("input.csv")
        _write_csv(input_path)

        result = runner.invoke(cli_module.app, [str(input_path), "--output", "out.csv"])

        assert result.exit_code == 1
        assert result.stdout == ""
        assert "boom" in result.stderr
