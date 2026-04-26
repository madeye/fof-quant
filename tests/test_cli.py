from typer.testing import CliRunner

from fof_quant.cli import app


def test_config_validate_command() -> None:
    result = CliRunner().invoke(
        app,
        ["config", "validate", "--config", "configs/example.yaml"],
    )

    assert result.exit_code == 0
    assert "Config valid: fof-quant-example" in result.stdout
