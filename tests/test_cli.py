from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("typer")
pytest.importorskip("pydantic")

from typer.testing import CliRunner

os.environ.setdefault("DD_TRACE_ENABLED", "false")
os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "false")

from cleanmydata.cli import app
from cleanmydata.cli_config import CLIConfig
from cleanmydata.constants import (
    DEFAULT_AUTO_OUTLIER_DETECT,
    DEFAULT_CLEAN_TEXT,
    DEFAULT_NORMALIZE_COLS,
    DEFAULT_OUTLIER_METHOD,
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


def test_cli_config_defaults_mapping(tmp_path):
    cli_cfg = CLIConfig(path=tmp_path / "input.csv")
    cleaning_cfg = cli_cfg.to_cleaning_config()

    assert cleaning_cfg.outliers == DEFAULT_OUTLIER_METHOD
    assert cleaning_cfg.normalize_cols is DEFAULT_NORMALIZE_COLS
    assert cleaning_cfg.clean_text is DEFAULT_CLEAN_TEXT
    assert cleaning_cfg.auto_outlier_detect is DEFAULT_AUTO_OUTLIER_DETECT
    assert cleaning_cfg.verbose is False


def test_cli_normal_prints_info_to_stdout(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path)])

    assert result.exit_code == EXIT_SUCCESS
    assert "Cleaned data saved as" in result.stdout
    assert result.stderr == ""
    assert output_path.exists()


def test_cli_normal_prints_errors_to_stderr():
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv"])

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    assert "Error loading dataset:" in result.stderr


def test_cli_quiet_no_progress_stdout(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "quiet_out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path), "--quiet"])

    assert result.exit_code == EXIT_SUCCESS
    assert result.stdout.strip() == str(output_path)
    assert "Cleaned data saved as" not in result.stdout
    assert result.stderr == ""


def test_cli_quiet_errors_still_stderr():
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv", "--quiet"])

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    assert "Error loading dataset:" in result.stderr


def test_cli_silent_empty_stdout(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "silent_out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path), "--silent"])

    assert result.exit_code == EXIT_SUCCESS
    assert result.stdout == ""
    assert result.stderr == ""
    assert output_path.exists()


def test_cli_silent_errors_still_stderr():
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv", "--silent"])

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    assert "Error loading dataset:" in result.stderr


def test_cli_silent_overrides_quiet_option(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "silent_out.csv"

    result = CliRunner().invoke(
        app, [str(input_path), "--output", str(output_path), "--quiet", "--silent"]
    )

    assert result.exit_code == EXIT_SUCCESS
    assert result.stdout == ""
    assert result.stderr == ""
    assert output_path.exists()


def test_cli_silent_correct_exit_code_on_error():
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv", "--silent"])

    assert result.exit_code == EXIT_IO_ERROR


def test_cli_exit_0_on_success(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path)])

    assert result.exit_code == EXIT_SUCCESS


def test_cli_exit_2_on_invalid_input(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise ValidationError("bad config")

    monkeypatch.setattr(cli_module, "clean_data", boom)

    input_path = _create_sample_csv()
    try:
        result = CliRunner().invoke(cli_module.app, [str(input_path), "--output", "out.csv"])
        assert result.exit_code == EXIT_INVALID_INPUT
    finally:
        input_path.unlink(missing_ok=True)


def test_cli_invalid_extension_returns_exit_invalid_input(tmp_path):
    bad_path = tmp_path / "input.parquet"

    result = CliRunner().invoke(app, [str(bad_path), "--output", str(tmp_path / "out.csv")])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert "Unsupported file format" in result.stderr


def test_cli_exit_3_on_file_not_found():
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv"])

    assert result.exit_code == EXIT_IO_ERROR
    assert "Error loading dataset:" in result.stderr


def test_cli_exit_2_on_excel_missing_dep(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise DependencyError(
            'Excel support is not installed. Install with: pip install "cleanmydata[excel]"'
        )

    monkeypatch.setattr(cli_module, "read_data", boom)

    result = CliRunner().invoke(cli_module.app, ["data.xlsx", "--output", "out.csv"])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert 'pip install "cleanmydata[excel]"' in result.stderr


def test_cli_csv_works_without_extras(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "csv_out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path)])

    assert result.exit_code == EXIT_SUCCESS
    assert output_path.exists()


def test_cli_excel_without_extra_shows_install_hint(monkeypatch):
    from cleanmydata import cli as cli_module

    def boom(*args, **kwargs):
        raise DependencyError(
            'Excel support is not installed. Install with: pip install "cleanmydata[excel]"'
        )

    monkeypatch.setattr(cli_module, "read_data", boom)

    result = CliRunner().invoke(cli_module.app, ["input.xlsx", "--output", "out.csv"])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert 'pip install "cleanmydata[excel]"' in result.stderr


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
