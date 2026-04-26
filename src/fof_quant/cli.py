from pathlib import Path
from typing import Annotated

import typer

from fof_quant.config import AppConfig, load_config

app = typer.Typer(help="ETF FOF research CLI.")
config_app = typer.Typer(help="Configuration commands.")
app.add_typer(config_app, name="config")


@app.callback()
def main() -> None:
    """Run ETF FOF research workflows."""


@config_app.command("validate")
def validate_config(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to a YAML configuration file.",
        ),
    ] = Path("configs/example.yaml"),
) -> None:
    """Validate a configuration file."""
    loaded: AppConfig = load_config(config)
    typer.echo(f"Config valid: {loaded.project.name}")
