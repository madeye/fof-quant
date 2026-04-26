from pathlib import Path

from typer.testing import CliRunner

from fof_quant.cli import app


def test_config_validate_command() -> None:
    result = CliRunner().invoke(
        app,
        ["config", "validate", "--config", "configs/example.yaml"],
    )

    assert result.exit_code == 0
    assert "Config valid: fof-quant-example" in result.stdout


def test_data_refresh_dry_run_command(tmp_path: Path) -> None:
    example_config = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        example_config.replace("cache_dir: cache/tushare", f"cache_dir: {tmp_path / 'cache'}"),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["data", "refresh", "--config", str(config_path), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "Data refresh dry run OK" in result.stdout
