from __future__ import annotations

import json
from pathlib import Path

from fof_quant.allocation.artifacts import write_allocation, write_scores
from fof_quant.allocation.engine import AllocationEngine
from fof_quant.backtest.artifacts import write_backtest_result
from fof_quant.backtest.engine import BacktestEngine
from fof_quant.config import AppConfig
from fof_quant.factors.artifacts import write_factor_snapshots
from fof_quant.factors.engine import FactorEngine, FactorInput
from fof_quant.factors.exposure import ExposureResolver
from fof_quant.pipeline_inputs import load_pipeline_inputs, universe_filter_from_config
from fof_quant.reports.generator import ReportGenerator
from fof_quant.scoring.engine import ScoringEngine


def run_offline_pipeline(config: AppConfig) -> dict[str, str]:
    output_dir = config.reports.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_pipeline_inputs(config)
    eligible_codes = universe_filter_from_config(config, inputs.rebalance_date).eligible_codes(
        inputs.candidates
    )
    factors = FactorEngine(
        ExposureResolver(inputs.fund_holdings, inputs.index_holdings)
    ).build(
        FactorInput(
            etf_codes=eligible_codes,
            rebalance_date=inputs.rebalance_date,
            stock_factors=inputs.stock_factors,
        )
    )
    scores = ScoringEngine(config.factors.weights).score(factors)
    allocation = AllocationEngine(
        min_holdings=config.strategy.min_holdings,
        max_weight=config.strategy.max_weight,
        cash_buffer=config.strategy.cash_buffer,
    ).allocate(scores)
    backtest = BacktestEngine(
        initial_cash=config.backtest.initial_cash,
        transaction_cost_bps=config.backtest.transaction_cost_bps,
        slippage_bps=config.backtest.slippage_bps,
    ).run(prices=inputs.etf_prices, allocation=allocation)
    report = ReportGenerator(config).generate()
    artifacts = {
        "factor_snapshots": str(
            write_factor_snapshots(factors, output_dir, inputs.rebalance_date)
        ),
        "scores": str(write_scores(scores, output_dir)),
        "allocation": str(write_allocation(allocation, output_dir)),
        "backtest": str(write_backtest_result(backtest, output_dir)),
        "excel_report": str(report.excel_path),
        "html_report": str(report.html_path),
    }
    manifest = write_artifact_manifest(output_dir, artifacts)
    artifacts["manifest"] = str(manifest)
    return artifacts


def write_artifact_manifest(output_dir: Path, artifacts: dict[str, str]) -> Path:
    path = output_dir / "artifact_manifest.json"
    path.write_text(
        json.dumps({"artifacts": artifacts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
