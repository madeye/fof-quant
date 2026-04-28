from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from fof_quant.allocation.artifacts import write_allocation, write_scores
from fof_quant.allocation.engine import AllocationEngine, AllocationPlan
from fof_quant.analysis.broad_index import analyze as analyze_broad_index
from fof_quant.analysis.broad_index import render_correlation, render_picks
from fof_quant.analysis.broad_index import write_csv as write_broad_csv
from fof_quant.analysis.csi300 import analyze as analyze_csi300
from fof_quant.analysis.csi300 import render_table, write_csv
from fof_quant.analysis.sweep import (
    QUICK_BANDS_PP,
    QUICK_SCHEMES,
    SCHEMES,
    render_sweep_table,
    run_sweep,
    write_sweep_csv,
    write_sweep_json,
)
from fof_quant.backtest.artifacts import write_backtest_result
from fof_quant.backtest.engine import BacktestEngine
from fof_quant.config import AppConfig, load_config
from fof_quant.data.broad_index import fetch_broad_index, load_broad_index
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
from fof_quant.pipeline_broad_index import (
    render_backtest_summary,
    render_rebalance_table,
    run_broad_index_backtest_pipeline,
    run_broad_index_pipeline,
)
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
web_app = typer.Typer(help="Web dashboard commands.")
app.add_typer(config_app, name="config")
app.add_typer(data_app, name="data")
app.add_typer(factors_app, name="factors")
app.add_typer(score_app, name="score")
app.add_typer(allocate_app, name="allocate")
app.add_typer(backtest_app, name="backtest")
app.add_typer(report_app, name="report")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(analyze_app, name="analyze")
app.add_typer(web_app, name="web")


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


@analyze_app.command("broad-index")
def analyze_broad_index_command(
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
    ] = Path("configs/broad_index.yaml"),
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh/--no-refresh",
            help="Pull fresh data from Tushare before analyzing.",
        ),
    ] = False,
) -> None:
    """Pick best ETF per broad-index sleeve and report the cross-sleeve correlation."""
    loaded = load_config(config)
    end_date = loaded.data.end_date or date.today()
    if refresh:
        result = fetch_broad_index(
            cache_dir=loaded.data.cache_dir,
            start_date=loaded.data.start_date,
            end_date=end_date,
        )
    else:
        result = load_broad_index(loaded.data.cache_dir)
    analysis = analyze_broad_index(result)
    csv_path = write_broad_csv(analysis, loaded.reports.output_dir)
    typer.echo(render_picks(analysis))
    typer.echo("\nBenchmark return correlation (252d):")
    typer.echo(render_correlation(analysis))
    typer.echo(f"\nWrote CSV: {csv_path}")


@analyze_app.command("sweep")
def analyze_sweep_command(
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
    ] = Path("configs/broad_index.yaml"),
    quick: Annotated[
        bool,
        typer.Option(
            "--quick/--full",
            help="Quick = 3 schemes × 3 bands; Full = 7 schemes × 6 bands.",
        ),
    ] = False,
    top: Annotated[
        int,
        typer.Option("--top", help="Show only the top N rows in the console."),
    ] = 10,
) -> None:
    """Sweep sleeve weight schemes × rebalance bands across cached history."""
    loaded = load_config(config)
    end_date = loaded.data.end_date or date.today()
    fetched = load_broad_index(loaded.data.cache_dir)
    schemes = (
        {name: SCHEMES[name] for name in QUICK_SCHEMES} if quick else SCHEMES
    )
    bands = QUICK_BANDS_PP if quick else None
    rows, benchmark, _ = run_sweep(
        fetched,
        start_date=loaded.data.start_date,
        end_date=end_date,
        initial_cash=loaded.backtest.initial_cash,
        schemes=schemes,
        bands_pp=bands or (1.0, 2.0, 3.0, 5.0, 7.0, 10.0),
        cash_buffer=loaded.strategy.cash_buffer,
        max_weight=loaded.strategy.max_weight,
        transaction_cost_bps=loaded.backtest.transaction_cost_bps,
        slippage_bps=loaded.backtest.slippage_bps,
    )
    csv_path = write_sweep_csv(rows, loaded.reports.output_dir, end_date=end_date)
    json_path = write_sweep_json(
        rows,
        loaded.reports.output_dir,
        start_date=loaded.data.start_date,
        end_date=end_date,
        benchmark=benchmark,
    )
    typer.echo(render_sweep_table(rows, benchmark, top=top))
    typer.echo(f"\nWrote CSV: {csv_path}")
    typer.echo(f"Wrote JSON: {json_path}")


@pipeline_app.command("broad-index")
def run_broad_index_command(
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
    ] = Path("configs/broad_index.yaml"),
    current: Annotated[
        Path | None,
        typer.Option(
            "--current",
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to a holdings JSON file. Omit to start from all-cash.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Force a full rebalance regardless of band drift (use semi-annually).",
        ),
    ] = False,
    abs_band_pp: Annotated[
        float,
        typer.Option("--abs-band-pp", help="Absolute drift band in percentage points."),
    ] = 1.0,
    rel_band_pct: Annotated[
        float,
        typer.Option("--rel-band-pct", help="Relative drift band in percent of target weight."),
    ] = 25.0,
    backtest: Annotated[
        bool,
        typer.Option(
            "--backtest/--no-backtest",
            help=(
                "Walk the rule monthly across cached history and emit NAV / Sharpe / MDD "
                "plus a per-rebalance log."
            ),
        ),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain/--no-explain",
            help="Append a Chinese LLM narrative section (uses LLM_* from .env).",
        ),
    ] = False,
) -> None:
    """Generate the broad-index FOF rebalance signal, or run the strategy as a backtest."""
    loaded = load_config(config)
    config_summary = _config_summary(loaded)
    if backtest:
        end_date = loaded.data.end_date or date.today()
        result, manifest_path, report, _narrative = run_broad_index_backtest_pipeline(
            cache_dir=loaded.data.cache_dir,
            output_dir=loaded.reports.output_dir,
            start_date=loaded.data.start_date,
            end_date=end_date,
            initial_cash=loaded.backtest.initial_cash,
            cash_buffer=loaded.strategy.cash_buffer,
            max_weight=loaded.strategy.max_weight,
            abs_band_pp=abs_band_pp,
            rel_band_pct=rel_band_pct,
            transaction_cost_bps=loaded.backtest.transaction_cost_bps,
            slippage_bps=loaded.backtest.slippage_bps,
            explain_with_llm=explain or loaded.reports.llm_explanations,
            config_summary=config_summary,
        )
        typer.echo(render_backtest_summary(result))
        typer.echo(f"\nManifest: {manifest_path}")
        if report is not None:
            typer.echo(f"Excel:    {report.excel_path}")
            typer.echo(f"HTML:     {report.html_path}")
        return
    artifacts = run_broad_index_pipeline(
        cache_dir=loaded.data.cache_dir,
        output_dir=loaded.reports.output_dir,
        holdings_path=current,
        initial_cash_if_empty=loaded.backtest.initial_cash,
        cash_buffer=loaded.strategy.cash_buffer,
        max_weight=loaded.strategy.max_weight,
        abs_band_pp=abs_band_pp,
        rel_band_pct=rel_band_pct,
        force_rebalance=force,
        explain_with_llm=explain or loaded.reports.llm_explanations,
        config_summary=config_summary,
    )
    typer.echo(render_rebalance_table(artifacts.rebalance_lines, artifacts.total_aum_cny))
    typer.echo(f"\nManifest: {artifacts.manifest_path}")
    if artifacts.report is not None:
        typer.echo(f"Excel:    {artifacts.report.excel_path}")
        typer.echo(f"HTML:     {artifacts.report.html_path}")
    if artifacts.llm_narrative:
        typer.echo("\nLLM narrative:\n" + artifacts.llm_narrative)


@web_app.command("serve")
def web_serve(
    reports_dir: Annotated[
        Path,
        typer.Option("--reports-dir", help="Directory holding existing CLI artifacts."),
    ] = Path("reports"),
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Cache dir used by triggered backtests."),
    ] = Path("cache/tushare"),
    broad_index_cache_dir: Annotated[
        Path,
        typer.Option(
            "--broad-index-cache-dir",
            help="Cache dir holding broad-index data (used to backfill legacy benchmark curves).",
        ),
    ] = Path("cache/broad_index"),
    db_path: Annotated[
        Path,
        typer.Option("--db", help="SQLite path for the run registry."),
    ] = Path("runs/runs.db"),
    host: Annotated[str, typer.Option(help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port.")] = 8000,
) -> None:
    """Start the web dashboard API.

    The Next.js dev server (under web/) consumes this API; start it separately
    with `pnpm --dir web dev`.
    """
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - import guard
        typer.echo("fastapi/uvicorn not installed; run `uv sync --extra web` first.")
        raise typer.Exit(code=1) from exc
    from fof_quant.web.app import create_app

    fastapi_app = create_app(
        reports_dir=reports_dir,
        cache_dir=cache_dir,
        broad_index_cache_dir=broad_index_cache_dir,
        db_path=db_path,
        scan_on_boot=True,
    )
    typer.echo(
        f"Dashboard API: http://{host}:{port}  •  start the UI with: pnpm --dir web dev"
    )
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def _config_summary(loaded: AppConfig) -> dict[str, object]:
    return {
        "project": loaded.project.name,
        "provider": loaded.data.provider,
        "start_date": loaded.data.start_date.isoformat(),
        "end_date": loaded.data.end_date.isoformat() if loaded.data.end_date else "",
        "benchmark": loaded.strategy.benchmark,
        "cash_buffer": loaded.strategy.cash_buffer,
        "max_weight": loaded.strategy.max_weight,
        "min_holdings": loaded.strategy.min_holdings,
        "transaction_cost_bps": loaded.backtest.transaction_cost_bps,
        "slippage_bps": loaded.backtest.slippage_bps,
        "llm_explanations": loaded.reports.llm_explanations,
    }
