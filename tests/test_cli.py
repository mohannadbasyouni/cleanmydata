from __future__ import annotations

import builtins
import importlib.util
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("typer")
pytest.importorskip("pydantic")

from typer.testing import CliRunner

os.environ.setdefault("DD_TRACE_ENABLED", "false")
os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "false")

from cleanmydata import cli as cli_module
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

PANDERA_AVAILABLE = importlib.util.find_spec("pandera") is not None


def _create_sample_csv() -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    tmp.write("name,age\nAlice,30\nBob,31\n")
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def test_cli_yaml_config_applied(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "verbose: true\noutliers: remove\nnormalize_cols: false\n", encoding="utf-8"
    )

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(output_path), "--config", str(config_path)],
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["outliers"] == "remove"
    assert captured["normalize_cols"] is False
    assert captured["verbose"] is True


def test_cli_env_overrides_yaml(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    config_path = tmp_path / "config.yml"
    config_path.write_text("verbose: true\noutliers: remove\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    env = os.environ.copy()
    env["CLEANMYDATA_VERBOSE"] = "false"
    env["CLEANMYDATA_OUTLIERS"] = "cap"

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(output_path), "--config", str(config_path)],
        env=env,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["verbose"] is False
    assert captured["outliers"] == "cap"


def test_cli_overrides_env_and_yaml(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    config_path = tmp_path / "config.yml"
    config_path.write_text("verbose: false\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    env = os.environ.copy()
    env["CLEANMYDATA_VERBOSE"] = "false"

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(output_path), "--config", str(config_path), "--verbose"],
        env=env,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["verbose"] is True


def test_cli_output_modes_yaml_quiet_env_silent(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("quiet: true\nverbose: true\n", encoding="utf-8")

    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv"},
        config_path=config_path,
        environ={"CLEANMYDATA_SILENT": "true"},
    )

    assert cfg.silent is True
    assert cfg.quiet is False
    assert cfg.verbose is False


def test_cli_output_modes_yaml_verbose_env_quiet(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("verbose: true\n", encoding="utf-8")

    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv"},
        config_path=config_path,
        environ={"CLEANMYDATA_QUIET": "true"},
    )

    assert cfg.quiet is True
    assert cfg.verbose is False


def test_cli_cli_overrides_env_and_yaml_output_modes(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("verbose: true\n", encoding="utf-8")

    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "input.csv", "verbose": False},
        config_path=config_path,
        environ={"CLEANMYDATA_VERBOSE": "true"},
    )

    assert cfg.verbose is False


def test_cli_input_without_suffix_defaults_to_csv(tmp_path):
    cfg = CLIConfig.from_sources(
        cli_args={"path": tmp_path / "dataset"}, environ={}, config_path=None
    )

    assert cfg.path.suffix == ".csv"
    assert cfg.path.name.endswith(".csv")


def test_cli_invalid_yaml_returns_exit_invalid_input(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    config_path = tmp_path / "bad.yml"
    config_path.write_text(":\n  - bad\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(tmp_path / "out.csv"), "--config", str(config_path)],
    )

    assert result.exit_code == EXIT_INVALID_INPUT
    assert "Invalid YAML" in result.stderr


def test_cli_missing_config_file_returns_exit_io_error(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    missing_config = tmp_path / "missing.yml"

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(tmp_path / "out.csv"), "--config", str(missing_config)],
    )

    assert result.exit_code == EXIT_IO_ERROR
    assert "Config file not found" in result.stderr


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


def test_cli_empty_input_exits_nonzero_and_prints_error(tmp_path):
    input_path = tmp_path / "empty.csv"
    input_path.write_text("name,age\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path)])

    assert result.exit_code == EXIT_GENERAL_ERROR
    assert "empty" in result.stderr.lower()
    assert not output_path.exists()


@pytest.mark.parametrize("extra_args", [[], ["--quiet"], ["--silent"]])
def test_cli_errors_only_on_stderr(extra_args):
    result = CliRunner().invoke(app, ["missing.csv", "--output", "out.csv", *extra_args])

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    assert result.stderr.startswith("Error:")


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


def test_cli_invalid_output_extension_returns_exit_invalid_input(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")

    result = CliRunner().invoke(app, [str(input_path), "--output", str(tmp_path / "out.txt")])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert "output" in result.stderr.lower()
    assert "supported" in result.stderr.lower()


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
    bad_path = tmp_path / "input.txt"

    result = CliRunner().invoke(app, [str(bad_path), "--output", str(tmp_path / "out.csv")])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert "Unsupported file format" in result.stderr


def test_cli_validation_error_message_clean(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    bad_output = tmp_path / "out.txt"

    result = CliRunner().invoke(app, [str(input_path), "--output", str(bad_output)])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert result.stdout == ""
    lowered = result.stderr.lower()
    assert lowered.startswith("error:")
    assert "unsupported output file format" in lowered
    assert "validation error for" not in lowered


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
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines[0].startswith("Error:")
    assert any(line.startswith("Hint:") for line in lines)
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
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines[0].startswith("Error:")
    assert any(line.startswith("Hint:") for line in lines)
    assert 'pip install "cleanmydata[excel]"' in result.stderr


def test_cli_default_output_matches_input_extension_parquet():
    pytest.importorskip("pyarrow")
    runner = CliRunner()

    with runner.isolated_filesystem():
        input_path = Path("sample.parquet")
        pd.DataFrame({"value": [1, 2]}).to_parquet(input_path, engine="pyarrow")

        result = runner.invoke(app, [str(input_path)])

        expected_output = Path("data") / "sample_cleaned.parquet"
        assert result.exit_code == EXIT_SUCCESS
        assert expected_output.exists()
        assert "sample_cleaned.parquet" in result.stdout


def test_cli_force_csv_output_from_parquet_input():
    pytest.importorskip("pyarrow")
    runner = CliRunner()

    with runner.isolated_filesystem():
        input_path = Path("source.parquet")
        pd.DataFrame({"value": [1]}).to_parquet(input_path, engine="pyarrow")
        output_name = "forced.csv"

        result = runner.invoke(app, [str(input_path), "--output", output_name])

        assert result.exit_code == EXIT_SUCCESS
        assert Path(output_name).exists()
        assert "forced.csv" in result.stdout


def test_cli_writes_excel_output_without_dependency(monkeypatch, tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.xlsx"

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openpyxl":
            raise ImportError("No openpyxl")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = CliRunner().invoke(app, [str(input_path), "--output", str(output_path)])

    assert result.exit_code == EXIT_INVALID_INPUT
    assert 'pip install "cleanmydata[excel]"' in result.stderr


def test_cli_schema_validation_failure_returns_exit_invalid_input(tmp_path):
    pytest.importorskip("pandera")
    input_path = tmp_path / "input.csv"
    input_path.write_text("age,name\n200,Alice\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    schema_path = tmp_path / "schema.yml"
    schema_path.write_text(
        "\n".join(
            [
                "columns:",
                "  age:",
                "    dtype: int",
                "    checks:",
                "      - in_range:",
                "          min: 0",
                "          max: 120",
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app, [str(input_path), "--output", str(output_path), "--schema", str(schema_path)]
    )

    assert result.exit_code == EXIT_INVALID_INPUT
    assert result.stdout == ""
    assert "Error:" in result.stderr
    assert "Schema validation failed" in result.stderr


def test_cli_schema_missing_pandera_shows_install_hint(monkeypatch, tmp_path):
    import cleanmydata.validation.schema as schema_module

    input_path = tmp_path / "input.csv"
    input_path.write_text("age,name\n10,Alice\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    schema_path = tmp_path / "schema.yml"
    schema_path.write_text("columns:\n  age:\n    dtype: int\n", encoding="utf-8")

    original_import = schema_module.importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "pandera":
            raise ImportError("pandera missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(schema_module.importlib, "import_module", fake_import)

    result = CliRunner().invoke(
        app, [str(input_path), "--output", str(output_path), "--schema", str(schema_path)]
    )

    assert result.exit_code == EXIT_INVALID_INPUT
    assert result.stdout == ""
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines[0].startswith("Error:")
    assert any(line.startswith("Hint:") for line in lines)
    assert 'pip install "cleanmydata[schema]"' in result.stderr


def test_cli_schema_invalid_yaml_returns_exit_invalid_input(monkeypatch, tmp_path):
    import cleanmydata.validation.schema as schema_module

    input_path = tmp_path / "input.csv"
    input_path.write_text("age,name\n10,Alice\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    schema_path = tmp_path / "schema.yml"
    schema_path.write_text(":\n  - bad\n", encoding="utf-8")

    # Ensure we test YAML parsing behavior regardless of pandera installation.
    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())

    result = CliRunner().invoke(
        app, [str(input_path), "--output", str(output_path), "--schema", str(schema_path)]
    )

    assert result.exit_code == EXIT_INVALID_INPUT
    assert result.stdout == ""
    assert result.stderr.startswith("Error:")
    assert "Invalid YAML in schema file" in result.stderr


def test_cli_schema_missing_file_returns_exit_io_error_and_hint(monkeypatch, tmp_path):
    import cleanmydata.validation.schema as schema_module

    input_path = tmp_path / "input.csv"
    input_path.write_text("age,name\n10,Alice\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    schema_path = tmp_path / "missing-schema.yml"

    monkeypatch.setattr(schema_module, "_require_pandera", lambda: object())

    result = CliRunner().invoke(
        app, [str(input_path), "--output", str(output_path), "--schema", str(schema_path)]
    )

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines[0].startswith("Error:")
    assert any(line.startswith("Hint:") for line in lines)
    assert "Schema file not found:" in result.stderr


def test_cli_recipe_applied_as_defaults(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"
    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text(
        "outliers: cap\nnormalize_cols: true\nclean_text: true\n", encoding="utf-8"
    )

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    result = CliRunner().invoke(
        cli_module.app,
        [str(input_path), "--output", str(output_path), "--recipe", str(recipe_path)],
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["outliers"] == "cap"
    assert captured["normalize_cols"] is True
    assert captured["clean_text"] is True


def test_cli_recipe_precedence(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text("outliers: cap\n", encoding="utf-8")

    config_path = tmp_path / "config.yml"
    config_path.write_text("outliers: remove\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    env = os.environ.copy()
    env["CLEANMYDATA_OUTLIERS"] = "cap"

    result = CliRunner().invoke(
        cli_module.app,
        [
            str(input_path),
            "--output",
            str(output_path),
            "--config",
            str(config_path),
            "--recipe",
            str(recipe_path),
            "--outliers",
            "remove",
        ],
        env=env,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["outliers"] == "remove"


def test_cli_precedence_chain_respects_cli_none(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text("outliers: remove\nnormalize_cols: false\n", encoding="utf-8")

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "outliers: cap\nclean_text: true\nnormalize_cols: true\n", encoding="utf-8"
    )

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    env = os.environ.copy()
    env["CLEANMYDATA_OUTLIERS"] = "remove"
    env["CLEANMYDATA_CLEAN_TEXT"] = "false"
    env["CLEANMYDATA_VERBOSE"] = "true"

    result = CliRunner().invoke(
        cli_module.app,
        [
            str(input_path),
            "--output",
            str(output_path),
            "--config",
            str(config_path),
            "--recipe",
            str(recipe_path),
            "--outliers",
            "none",
        ],
        env=env,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["outliers"] is None  # CLI explicit none overrides env/yaml/recipe
    assert captured["clean_text"] is False  # Env overrides YAML default
    assert captured["normalize_cols"] is True  # YAML overrides recipe default
    assert captured["verbose"] is True  # Env applied when CLI flag omitted


def test_cli_recipe_save_creates_yaml(tmp_path):
    recipe_path = tmp_path / "saved_recipe.yml"

    result = CliRunner().invoke(
        app,
        [
            "recipe",
            "save",
            str(recipe_path),
            "--outliers",
            "remove",
            "--no-normalize-cols",
            "--no-clean-text",
            "--no-auto-outlier-detect",
        ],
    )

    assert result.exit_code == EXIT_SUCCESS
    assert recipe_path.exists()


def test_cli_recipe_save_missing_directory_returns_exit_io_error(tmp_path):
    recipe_path = tmp_path / "missing" / "recipe.yml"

    result = CliRunner().invoke(app, ["recipe", "save", str(recipe_path)])

    assert result.exit_code == EXIT_IO_ERROR
    assert result.stdout == ""
    assert result.stderr.startswith("Error:")


def test_cli_recipe_load_applies_recipe(tmp_path, monkeypatch):
    input_path = tmp_path / "input.csv"
    input_path.write_text("name,age\nAlice,30\n", encoding="utf-8")
    output_path = tmp_path / "out.csv"

    recipe_path = tmp_path / "recipe.yml"
    recipe_path.write_text("outliers: remove\nnormalize_cols: false\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_clean_data(df, **kwargs):
        captured.update(kwargs)
        return df, {}

    monkeypatch.setattr(cli_module, "clean_data", fake_clean_data)

    result = CliRunner().invoke(
        cli_module.app,
        ["recipe", "load", str(recipe_path), str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == EXIT_SUCCESS
    assert captured["outliers"] == "remove"
    assert captured["normalize_cols"] is False


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
