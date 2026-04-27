from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from fof_quant.backtest.metrics import PerformanceMetrics
from fof_quant.backtest_broad_index import (
    BroadIndexBacktest,
    precompute_pit_cache,
    run_broad_index_backtest,
)
from fof_quant.data.broad_index import BroadIndexFetchResult

# Predefined sleeve weight schemes. All sum to 1.0 (cash buffer is taken on top).
SCHEMES: dict[str, dict[str, float]] = {
    "balanced_5": {
        "中证A500": 0.35,
        "中证1000": 0.20,
        "创业板指": 0.15,
        "科创50": 0.15,
        "中证红利低波": 0.15,
    },
    "core_300_only": {"沪深300": 1.00},
    "core_satellite": {
        "沪深300": 0.50,
        "中证1000": 0.20,
        "创业板指": 0.15,
        "中证红利低波": 0.15,
    },
    "growth_tilt": {
        "中证A500": 0.20,
        "中证1000": 0.20,
        "创业板指": 0.30,
        "科创50": 0.20,
        "中证红利低波": 0.10,
    },
    "defensive": {
        "上证50": 0.30,
        "中证A500": 0.30,
        "中证红利低波": 0.30,
        "中证1000": 0.10,
    },
    "equal_5": {
        "中证A500": 0.20,
        "中证1000": 0.20,
        "创业板指": 0.20,
        "科创50": 0.20,
        "中证红利低波": 0.20,
    },
    "dividend_heavy": {
        "中证A500": 0.30,
        "中证1000": 0.15,
        "创业板指": 0.10,
        "科创50": 0.10,
        "中证红利低波": 0.35,
    },
}

DEFAULT_BANDS_PP: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 7.0, 10.0)
QUICK_BANDS_PP: tuple[float, ...] = (3.0, 5.0, 10.0)
QUICK_SCHEMES: tuple[str, ...] = ("balanced_5", "core_300_only", "growth_tilt")


@dataclass(frozen=True)
class SweepRow:
    scheme: str
    band_pp: float
    final_nav: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float
    calmar: float
    tracking_error: float
    rebalances: int
    avg_turnover_pct: float
    total_cost_cny: float


def run_sweep(
    fetched: BroadIndexFetchResult,
    *,
    start_date: date,
    end_date: date,
    initial_cash: float,
    schemes: dict[str, dict[str, float]] | None = None,
    bands_pp: Iterable[float] = DEFAULT_BANDS_PP,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
    rel_band_pct: float = 25.0,
    transaction_cost_bps: float = 2.0,
    slippage_bps: float = 1.0,
    benchmark_label: str = "沪深300",
) -> tuple[list[SweepRow], PerformanceMetrics | None, list[BroadIndexBacktest]]:
    """Walk every (scheme, band) combination across the cached history.
    The PIT analyzer is computed once and reused across combinations, so the
    sweep cost grows linearly with combinations rather than with combinations
    times rebalance dates.

    Returns (rows, benchmark_metrics, all_backtests). The all_backtests list
    is in the same order as rows for downstream curve inspection.
    """
    schemes_to_run = schemes or SCHEMES
    bands = tuple(bands_pp)
    pit_cache = precompute_pit_cache(
        fetched, start_date=start_date, end_date=end_date
    )

    rows: list[SweepRow] = []
    backtests: list[BroadIndexBacktest] = []
    benchmark_metrics: PerformanceMetrics | None = None

    for scheme_name, weights in schemes_to_run.items():
        for band in bands:
            bt = run_broad_index_backtest(
                fetched,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                sleeve_weights=weights,
                cash_buffer=cash_buffer,
                max_weight=max_weight,
                abs_band_pp=band,
                rel_band_pct=rel_band_pct,
                transaction_cost_bps=transaction_cost_bps,
                slippage_bps=slippage_bps,
                benchmark_label=benchmark_label,
                pit_analysis_provider=pit_cache.get,
            )
            backtests.append(bt)
            avg_turnover = (
                sum(r.turnover_pct for r in bt.rebalances) / len(bt.rebalances)
                if bt.rebalances
                else 0.0
            )
            total_cost = sum(r.cost_cny for r in bt.rebalances)
            final_nav = bt.curve[-1].nav if bt.curve else initial_cash
            rows.append(
                SweepRow(
                    scheme=scheme_name,
                    band_pp=band,
                    final_nav=final_nav,
                    cagr=bt.metrics.annualized_return,
                    vol=bt.metrics.volatility,
                    sharpe=bt.metrics.sharpe,
                    max_drawdown=bt.metrics.max_drawdown,
                    calmar=bt.metrics.calmar,
                    tracking_error=bt.metrics.tracking_error,
                    rebalances=len(bt.rebalances),
                    avg_turnover_pct=avg_turnover,
                    total_cost_cny=total_cost,
                )
            )
            if benchmark_metrics is None and bt.benchmark_metrics is not None:
                benchmark_metrics = bt.benchmark_metrics

    return rows, benchmark_metrics, backtests


def render_sweep_table(
    rows: list[SweepRow],
    benchmark: PerformanceMetrics | None = None,
    *,
    sort_by: str = "sharpe",
    top: int | None = None,
) -> str:
    if not rows:
        return "(no sweep results)"
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            -getattr(r, sort_by),
            r.scheme,
            r.band_pp,
        ),
    )
    if top is not None:
        sorted_rows = sorted_rows[:top]

    header = (
        f"{'rank':>4s}  {'scheme':16s}  {'band':>5s}  {'CAGR%':>7s}  "
        f"{'Vol%':>6s}  {'Sharpe':>6s}  {'MDD%':>7s}  {'Calmar':>6s}  "
        f"{'TE%':>6s}  {'rebal':>5s}  {'turn%':>6s}  {'cost¥':>10s}"
    )
    rule = "-" * len(header)
    lines = [header, rule]
    for i, row in enumerate(sorted_rows, start=1):
        lines.append(
            f"{i:>4d}  {row.scheme:16s}  {row.band_pp:5.1f}  "
            f"{row.cagr * 100:7.2f}  {row.vol * 100:6.2f}  {row.sharpe:6.2f}  "
            f"{row.max_drawdown * 100:7.2f}  {row.calmar:6.2f}  "
            f"{row.tracking_error * 100:6.2f}  {row.rebalances:5d}  "
            f"{row.avg_turnover_pct * 100:6.1f}  {row.total_cost_cny:10,.0f}"
        )
    if benchmark is not None:
        lines.append(rule)
        lines.append(
            f"  benchmark (沪深300 TR):  CAGR {benchmark.annualized_return * 100:6.2f}%  "
            f"Vol {benchmark.volatility * 100:5.2f}%  Sharpe {benchmark.sharpe:5.2f}  "
            f"MDD {benchmark.max_drawdown * 100:6.2f}%"
        )
    return "\n".join(lines)


def write_sweep_csv(
    rows: list[SweepRow],
    output_dir: Path,
    *,
    end_date: date,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"sweep_{end_date:%Y%m%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "scheme",
                "band_pp",
                "final_nav",
                "cagr_pct",
                "vol_pct",
                "sharpe",
                "max_drawdown_pct",
                "calmar",
                "tracking_error_pct",
                "rebalances",
                "avg_turnover_pct",
                "total_cost_cny",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.scheme,
                    r.band_pp,
                    f"{r.final_nav:.2f}",
                    f"{r.cagr * 100:.4f}",
                    f"{r.vol * 100:.4f}",
                    f"{r.sharpe:.4f}",
                    f"{r.max_drawdown * 100:.4f}",
                    f"{r.calmar:.4f}",
                    f"{r.tracking_error * 100:.4f}",
                    r.rebalances,
                    f"{r.avg_turnover_pct * 100:.4f}",
                    f"{r.total_cost_cny:.2f}",
                ]
            )
    return path


def write_sweep_json(
    rows: list[SweepRow],
    output_dir: Path,
    *,
    start_date: date,
    end_date: date,
    benchmark: PerformanceMetrics | None = None,
) -> Path:
    """Emit a JSON sibling to the sweep CSV for the dashboard heatmap.

    Schema mirrors ``backtest_broad_index._backtest_manifest`` enough to share
    helpers but adds the sweep-specific axes (schemes, bands) and per-cell row
    payload so the frontend can render a heatmap without re-parsing the CSV.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    schemes_in_order: list[str] = []
    bands_in_order: list[float] = []
    for row in rows:
        if row.scheme not in schemes_in_order:
            schemes_in_order.append(row.scheme)
        if row.band_pp not in bands_in_order:
            bands_in_order.append(row.band_pp)
    payload: dict[str, object] = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "schemes": schemes_in_order,
        "bands_pp": bands_in_order,
        "rows": [asdict(row) for row in rows],
        "benchmark": _benchmark_payload(benchmark),
    }
    path = output_dir / f"sweep_{end_date:%Y%m%d}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _benchmark_payload(benchmark: PerformanceMetrics | None) -> dict[str, float] | None:
    if benchmark is None:
        return None
    return {
        "total_return": benchmark.total_return,
        "annualized_return": benchmark.annualized_return,
        "volatility": benchmark.volatility,
        "sharpe": benchmark.sharpe,
        "max_drawdown": benchmark.max_drawdown,
        "calmar": benchmark.calmar,
        "win_rate": benchmark.win_rate,
        "tracking_error": benchmark.tracking_error,
    }


__all__ = [
    "DEFAULT_BANDS_PP",
    "QUICK_BANDS_PP",
    "QUICK_SCHEMES",
    "SCHEMES",
    "SweepRow",
    "render_sweep_table",
    "run_sweep",
    "write_sweep_csv",
    "write_sweep_json",
]
