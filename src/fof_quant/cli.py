from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from fof_quant.allocation.artifacts import write_allocation, write_scores
from fof_quant.allocation.engine import AllocationEngine, AllocationPlan
from fof_quant.analysis.csi300 import analyze as analyze_csi300
from fof_quant.analysis.csi300 import render_table, write_csv
from fof_quant.backtest.artifacts import write_backtest_result
from fof_quant.backtest.engine import BacktestEngine
from fof_quant.config import AppConfig, load_config
from fof_quant.data.cache import CacheStore
from fof_quant.data.csi300 import fetch_csi300, load_csi300
from fof_quant.data.provider import DataRequest
from fof_quant.data.refresh import DEFAULT_DATASETS, refresh_datasets
from fof_quant.data.tushare import build_tushare_provider
from fof_quant.factors.artifacts import write_factor_snapshots
from fof_quant.factors.engine import FactorEngine, FactorInput
from fof_quant.factors.exposure import ExposureResolver
from fof_quant.logging import configure_logging
from fof_quant.pipeline import run_offline_pipeline
from fof_quant.reports.generator import ReportGenerator
from fof_quant.scoring.engine import ScoringEngine

app = typer.Typer(help="ETF FOF research CLI.")
config_app = typer.Typer(help="Configuration commands.")
data_app = typer.Typer(help="Data commands.")
factors_app = typer.Typer(help="Factor commands.")
score_app = typer.Typer(help="Scoring commands.")
allocate_app = typer.Typer(help="Allocation commands.")
backtest_app = typer.Typer(help="Backtest commands.")
report_app = typer.Typer(help="Report commands.")
pipeline_app = typer.Typer(help="Pipeline commands.")
analyze_app = typer.Typer(help="Analysis commands.")
app.add_typer(config_app, name="config")
app.add_typer(data_app, name="data")
app.add_typer(factors_app, name="factors")
app.add_typer(score_app, name="score")
app.add_typer(allocate_app, name="allocate")
app.add_typer(backtest_app, name="backtest")
app.add_typer(report_app, name="report")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(analyze_app, name="analyze")


@app.callback()
def main(
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Python logging level."),
    ] = "INFO",
) -> None:
    """Run ETF FOF research workflows."""
    configure_logging(log_level)


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


@factors_app.command("build")
def build_factors(
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
    """Build ETF factor snapshots from cached inputs."""
    loaded = load_config(config)
    engine = FactorEngine(ExposureResolver(fund_holdings=[], index_holdings=[]))
    snapshots = engine.build(
        FactorInput(etf_codes=[], rebalance_date=loaded.data.start_date, stock_factors=[])
    )
    path = write_factor_snapshots(snapshots, loaded.reports.output_dir, loaded.data.start_date)
    typer.echo(f"Wrote factor snapshots: {path}")


@score_app.command("run")
def run_scoring(
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
    """Run ETF scoring and allocation."""
    loaded = load_config(config)
    scores = ScoringEngine(loaded.factors.weights).score([])
    plan = AllocationEngine(
        min_holdings=loaded.strategy.min_holdings,
        max_weight=loaded.strategy.max_weight,
        cash_buffer=loaded.strategy.cash_buffer,
    ).allocate(scores)
    score_path = write_scores(scores, loaded.reports.output_dir)
    allocation_path = write_allocation(plan, loaded.reports.output_dir)
    typer.echo(f"Wrote scores: {score_path}")
    typer.echo(f"Wrote allocation: {allocation_path}")


@allocate_app.command("run")
def run_allocation(
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
    """Run allocation from prepared score artifacts."""
    loaded = load_config(config)
    plan = AllocationEngine(
        min_holdings=loaded.strategy.min_holdings,
        max_weight=loaded.strategy.max_weight,
        cash_buffer=loaded.strategy.cash_buffer,
    ).allocate([])
    allocation_path = write_allocation(plan, loaded.reports.output_dir)
    typer.echo(f"Wrote allocation: {allocation_path}")


@backtest_app.command("run")
def run_backtest(
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
    """Run a backtest from prepared artifacts."""
    loaded = load_config(config)
    engine = BacktestEngine(
        initial_cash=loaded.backtest.initial_cash,
        transaction_cost_bps=loaded.backtest.transaction_cost_bps,
        slippage_bps=loaded.backtest.slippage_bps,
    )
    result = engine.run(
        prices=[],
        allocation=AllocationPlan([], cash_weight=1.0, constraint_checks={}),
    )
    path = write_backtest_result(result, loaded.reports.output_dir)
    typer.echo(f"Wrote backtest: {path}")


@report_app.command("build")
def build_report(
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
    """Build Excel and HTML reports."""
    bundle = ReportGenerator(load_config(config)).generate()
    typer.echo(f"Wrote Excel report: {bundle.excel_path}")
    typer.echo(f"Wrote HTML report: {bundle.html_path}")


@pipeline_app.command("run")
def run_pipeline(
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
    """Run the offline artifact pipeline."""
    artifacts = run_offline_pipeline(load_config(config))
    typer.echo(f"Wrote artifact manifest: {artifacts['manifest']}")


@analyze_app.command("csi300")
def analyze_csi300_command(
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
    ] = Path("configs/csi300.yaml"),
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh/--no-refresh",
            help="Pull fresh data from Tushare before analyzing.",
        ),
    ] = False,
) -> None:
    """Analyze CSI 300 ETFs and write a ranked report."""
    loaded = load_config(config)
    end_date = loaded.data.end_date or date.today()
    if refresh:
        result = fetch_csi300(
            cache_dir=loaded.data.cache_dir,
            start_date=loaded.data.start_date,
            end_date=end_date,
        )
    else:
        result = load_csi300(loaded.data.cache_dir)
    analysis = analyze_csi300(result)
    csv_path = write_csv(analysis, loaded.reports.output_dir)
    typer.echo(render_table(analysis))
    typer.echo(f"\nWrote CSV: {csv_path}")
