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


def test_factors_build_command(tmp_path: Path) -> None:
    example_config = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    report_dir = tmp_path / "reports"
    config_path.write_text(
        example_config.replace("output_dir: reports", f"output_dir: {report_dir}"),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["factors", "build", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Wrote factor snapshots" in result.stdout
    assert (report_dir / "factor_snapshots_2018-01-01.json").exists()


def test_score_run_command(tmp_path: Path) -> None:
    example_config = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    report_dir = tmp_path / "reports"
    config_path.write_text(
        example_config.replace("output_dir: reports", f"output_dir: {report_dir}"),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["score", "run", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert (report_dir / "scores.json").exists()
    assert (report_dir / "allocation.json").exists()
