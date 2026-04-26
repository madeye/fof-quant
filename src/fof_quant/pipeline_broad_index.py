from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from fof_quant.allocation.engine import AllocationPlan
from fof_quant.analysis.attribution import (
    attribution_payload,
    compute_attribution,
    render_attribution_table,
    render_attribution_top_drawdown,
)
from fof_quant.analysis.broad_index import (
    BroadIndexAnalysis,
)
from fof_quant.analysis.broad_index import (
    analyze as analyze_broad_index,
)
from fof_quant.analysis.broad_index_allocation import (
    DEFAULT_SLEEVE_WEIGHTS,
    build_target_plan,
    sleeve_by_code,
)
from fof_quant.backtest_broad_index import BroadIndexBacktest, run_broad_index_backtest
from fof_quant.data.broad_index import BroadIndexFetchResult, load_broad_index
from fof_quant.env import llm_env
from fof_quant.portfolio.holdings import CurrentPortfolio, load_holdings
from fof_quant.portfolio.rebalance import RebalanceLine, compute_rebalance
from fof_quant.reports.broad_index_report import (
    ReportBundle,
    write_backtest_report,
    write_signal_report,
)
from fof_quant.reports.llm import explain_broad_index


@dataclass(frozen=True)
class BroadIndexRunArtifacts:
    target_plan: AllocationPlan
    rebalance_lines: list[RebalanceLine]
    total_aum_cny: float
    manifest_path: Path
    report: ReportBundle | None = None
    llm_narrative: str = ""


def run_broad_index_pipeline(
    *,
    cache_dir: Path,
    output_dir: Path,
    holdings_path: Path | None,
    initial_cash_if_empty: float,
    sleeve_weights: dict[str, float] | None = None,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
    abs_band_pp: float = 5.0,
    rel_band_pct: float = 25.0,
    force_rebalance: bool = False,
    write_report: bool = True,
    explain_with_llm: bool = False,
    config_summary: dict[str, object] | None = None,
) -> BroadIndexRunArtifacts:
    weights = sleeve_weights or DEFAULT_SLEEVE_WEIGHTS
    fetched = load_broad_index(cache_dir)
    analysis = analyze_broad_index(fetched)
    target_plan = build_target_plan(
        analysis,
        sleeve_weights=weights,
        cash_buffer=cash_buffer,
        max_weight=max_weight,
    )
    last_price = _last_close_per_code(fetched)
    portfolio = (
        load_holdings(holdings_path)
        if holdings_path is not None
        else CurrentPortfolio.empty(as_of=analysis.as_of, cash_cny=initial_cash_if_empty)
    )
    aum = portfolio.total_aum(last_price)
    current_weights = portfolio.weights(last_price)
    lines = compute_rebalance(
        target_plan,
        sleeve_by_code=sleeve_by_code(analysis),
        current_weights=current_weights,
        last_price=last_price,
        total_aum_cny=aum,
        abs_band_pp=abs_band_pp,
        rel_band_pct=rel_band_pct,
        force=force_rebalance,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_payload(analysis, target_plan, lines, aum, weights)
    manifest_path = output_dir / f"broad_index_rebalance_{analysis.as_of:%Y%m%d}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    narrative = (
        explain_broad_index(enabled=True, env=llm_env(), payload=manifest)
        if explain_with_llm
        else ""
    )
    report = (
        write_signal_report(
            output_dir=output_dir,
            config_summary=config_summary or {},
            analysis=analysis,
            target_plan=target_plan,
            rebalance_lines=lines,
            total_aum_cny=aum,
            sleeve_weights=weights,
            llm_narrative=narrative,
        )
        if write_report
        else None
    )
    return BroadIndexRunArtifacts(
        target_plan=target_plan,
        rebalance_lines=lines,
        total_aum_cny=aum,
        manifest_path=manifest_path,
        report=report,
        llm_narrative=narrative,
    )


def render_rebalance_table(lines: list[RebalanceLine], total_aum_cny: float) -> str:
    header = (
        f"Rebalance signal — total AUM ¥{total_aum_cny:,.0f}\n"
        f"{'sleeve':12s}  {'code':10s}  {'tgt%':>6s}  {'cur%':>6s}  "
        f"{'drift_pp':>8s}  {'action':>6s}  {'Δnotional¥':>12s}  {'Δshares':>10s}"
    )
    rule = "-" * len(header.splitlines()[1])
    body = []
    for line in lines:
        body.append(
            f"{line.sleeve:12s}  {line.ts_code:10s}  "
            f"{line.target_weight * 100:6.2f}  {line.current_weight * 100:6.2f}  "
            f"{line.drift_pp:+8.2f}  {line.action:>6s}  "
            f"{line.delta_notional_cny:12,.0f}  {line.delta_shares_lot100:+10d}"
        )
    return "\n".join([header, rule, *body])


def _last_close_per_code(fetched: BroadIndexFetchResult) -> dict[str, float]:
    latest: dict[str, tuple[str, float]] = {}
    for row in fetched.etf_daily.rows:
        code = str(row["ts_code"])
        trade_date = str(row["trade_date"])
        close = row.get("close")
        if close is None:
            continue
        prior = latest.get(code)
        if prior is None or trade_date > prior[0]:
            latest[code] = (trade_date, float(close))
    return {code: price for code, (_, price) in latest.items()}


def _manifest_payload(
    analysis: BroadIndexAnalysis,
    target_plan: AllocationPlan,
    lines: list[RebalanceLine],
    total_aum_cny: float,
    sleeve_weights: dict[str, float],
) -> dict[str, object]:
    return {
        "as_of": analysis.as_of.isoformat(),
        "total_aum_cny": total_aum_cny,
        "sleeve_weights": sleeve_weights,
        "target_plan": {
            "holdings": [asdict(row) for row in target_plan.holdings],
            "cash_weight": target_plan.cash_weight,
            "constraint_checks": target_plan.constraint_checks,
        },
        "rebalance_lines": [asdict(line) for line in lines],
        "trade_count": sum(1 for line in lines if line.action not in ("hold",)),
    }


def run_broad_index_backtest_pipeline(
    *,
    cache_dir: Path,
    output_dir: Path,
    start_date: date,
    end_date: date,
    initial_cash: float,
    sleeve_weights: dict[str, float] | None = None,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
    abs_band_pp: float = 5.0,
    rel_band_pct: float = 25.0,
    transaction_cost_bps: float = 2.0,
    slippage_bps: float = 1.0,
    benchmark_label: str = "沪深300",
    write_report: bool = True,
    explain_with_llm: bool = False,
    config_summary: dict[str, object] | None = None,
) -> tuple[BroadIndexBacktest, Path, ReportBundle | None, str]:
    fetched = load_broad_index(cache_dir)
    backtest = run_broad_index_backtest(
        fetched,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        sleeve_weights=sleeve_weights,
        cash_buffer=cash_buffer,
        max_weight=max_weight,
        abs_band_pp=abs_band_pp,
        rel_band_pct=rel_band_pct,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        benchmark_label=benchmark_label,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _backtest_manifest(backtest)
    manifest_path = output_dir / f"broad_index_backtest_{end_date:%Y%m%d}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    narrative = (
        explain_broad_index(enabled=True, env=llm_env(), payload=manifest)
        if explain_with_llm
        else ""
    )
    report = None
    if write_report:
        analysis = analyze_broad_index(fetched)
        report = write_backtest_report(
            output_dir=output_dir,
            config_summary=config_summary or {},
            analysis=analysis,
            backtest=backtest,
            sleeve_weights=sleeve_weights or DEFAULT_SLEEVE_WEIGHTS,
            llm_narrative=narrative,
        )
    return backtest, manifest_path, report, narrative


def render_backtest_summary(backtest: BroadIndexBacktest) -> str:
    if not backtest.curve:
        return "Backtest produced no data."
    m = backtest.metrics
    bench = backtest.benchmark_metrics
    avg_turn = (
        sum(r.turnover_pct for r in backtest.rebalances) / len(backtest.rebalances) * 100
        if backtest.rebalances
        else 0.0
    )
    lines = [
        f"Backtest: {backtest.curve[0].trade_date} → {backtest.curve[-1].trade_date}",
        f"  Final NAV: {backtest.curve[-1].nav:,.0f}  ({m.total_return * 100:+.2f}% total)",
        (
            f"  CAGR: {m.annualized_return * 100:+.2f}%   Vol: {m.volatility * 100:.2f}%   "
            f"Sharpe: {m.sharpe:.2f}   MaxDD: {m.max_drawdown * 100:.2f}%   "
            f"Calmar: {m.calmar:.2f}"
        ),
        f"  Win rate: {m.win_rate * 100:.1f}%   TE vs benchmark: {m.tracking_error * 100:.2f}%",
        f"  Rebalances triggered: {len(backtest.rebalances)}   "
        f"Avg turnover/rebalance: {avg_turn:.1f}%",
    ]
    if bench is not None:
        lines.append(
            f"  Benchmark: total {bench.total_return * 100:+.2f}%   "
            f"CAGR {bench.annualized_return * 100:+.2f}%   "
            f"Sharpe {bench.sharpe:.2f}   MaxDD {bench.max_drawdown * 100:.2f}%"
        )
    attribution = compute_attribution(backtest)
    if attribution.sleeves:
        lines.append("")
        lines.append("Sleeve attribution:")
        lines.append(render_attribution_table(attribution))
        lines.append("")
        lines.append(render_attribution_top_drawdown(backtest, top_n_days=5))
    return "\n".join(lines)


def _backtest_manifest(backtest: BroadIndexBacktest) -> dict[str, object]:
    attribution = compute_attribution(backtest)
    return {
        "as_of_start": backtest.curve[0].trade_date.isoformat() if backtest.curve else None,
        "as_of_end": backtest.curve[-1].trade_date.isoformat() if backtest.curve else None,
        "metrics": _metrics_payload(backtest.metrics),
        "benchmark_metrics": _metrics_payload(backtest.benchmark_metrics)
        if backtest.benchmark_metrics
        else None,
        "attribution": attribution_payload(attribution),
        "rebalances": [
            {
                "trade_date": r.trade_date.isoformat(),
                "nav_before": r.nav_before,
                "turnover_pct": r.turnover_pct,
                "cost_cny": r.cost_cny,
                "triggered_codes": r.triggered_codes,
                "target_weights": r.target_weights,
                "realized_weights_after": r.realized_weights_after,
            }
            for r in backtest.rebalances
        ],
        "curve": [
            {
                "trade_date": p.trade_date.isoformat(),
                "nav": p.nav,
                "daily_return": p.daily_return,
                "drawdown": p.drawdown,
            }
            for p in backtest.curve
        ],
    }


def _metrics_payload(metrics: object) -> dict[str, float] | None:
    if metrics is None:
        return None
    return {
        "total_return": getattr(metrics, "total_return", 0.0),
        "annualized_return": getattr(metrics, "annualized_return", 0.0),
        "volatility": getattr(metrics, "volatility", 0.0),
        "sharpe": getattr(metrics, "sharpe", 0.0),
        "max_drawdown": getattr(metrics, "max_drawdown", 0.0),
        "calmar": getattr(metrics, "calmar", 0.0),
        "win_rate": getattr(metrics, "win_rate", 0.0),
        "tracking_error": getattr(metrics, "tracking_error", 0.0),
    }


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"object of type {type(value)} is not JSON serializable")
