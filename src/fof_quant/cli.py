from pathlib import Path
from typing import Annotated

import typer

from fof_quant.config import AppConfig, load_config
from fof_quant.data.cache import CacheStore
from fof_quant.data.provider import DataRequest
from fof_quant.data.refresh import DEFAULT_DATASETS, refresh_datasets
from fof_quant.data.tushare import build_tushare_provider

app = typer.Typer(help="ETF FOF research CLI.")
config_app = typer.Typer(help="Configuration commands.")
data_app = typer.Typer(help="Data commands.")
app.add_typer(config_app, name="config")
app.add_typer(data_app, name="data")


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


@data_app.command("refresh")
def refresh_data(
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
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Validate config and prepare cache directories without provider calls.",
        ),
    ] = False,
) -> None:
    """Refresh provider data into the local cache."""
    loaded: AppConfig = load_config(config)
    cache = CacheStore(loaded.data.cache_dir)
    cache.ensure_dirs()
    if dry_run:
        typer.echo(f"Data refresh dry run OK: cache_dir={loaded.data.cache_dir}")
        return
    requests = [
        DataRequest(
            dataset=dataset,
            start_date=loaded.data.start_date,
            end_date=loaded.data.end_date,
        )
        for dataset in DEFAULT_DATASETS
    ]
    metadata = refresh_datasets(
        provider=build_tushare_provider(),
        cache=cache,
        requests=requests,
    )
    typer.echo(f"Refreshed {len(metadata)} datasets into {loaded.data.cache_dir}")
