from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import ZipFile

from fof_quant.allocation.engine import AllocationPlan, AllocationRow
from fof_quant.analysis.broad_index import BroadIndexAnalysis, SleevePick
from fof_quant.backtest.metrics import PerformanceMetrics
from fof_quant.backtest_broad_index import BroadIndexBacktest, CurvePoint, RebalanceEvent
from fof_quant.data.broad_index import IndexSpec
from fof_quant.portfolio.rebalance import RebalanceLine
from fof_quant.reports.broad_index_report import (
    write_backtest_report,
    write_signal_report,
)


def _spec(label: str = "沪深300") -> IndexSpec:
    return IndexSpec(label, "000300.SH", "H00300.CSI", r"^沪深300指数$")


def _empty_analysis() -> BroadIndexAnalysis:
    spec = _spec()
    return BroadIndexAnalysis(
        as_of=date(2026, 4, 24),
        sleeve_picks=[SleevePick(spec=spec, pick=None)],
    )


def test_signal_report_writes_valid_xlsx_and_html(tmp_path: Path) -> None:
    plan = AllocationPlan(
        holdings=[AllocationRow(etf_code="510300.SH", weight=0.5, score=1.0, reason="pick")],
        cash_weight=0.5,
        constraint_checks={"min_holdings": True},
    )
    line = RebalanceLine(
        ts_code="510300.SH",
        sleeve="沪深300",
        target_weight=0.5,
        current_weight=0.0,
        drift_pp=-50.0,
        drift_rel_pct=-100.0,
        action="open",
        target_notional_cny=500_000.0,
        delta_notional_cny=500_000.0,
        last_price=4.0,
        delta_shares_lot100=125_000,
    )
    bundle = write_signal_report(
        output_dir=tmp_path,
        config_summary={"project": "test"},
        analysis=_empty_analysis(),
        target_plan=plan,
        rebalance_lines=[line],
        total_aum_cny=1_000_000.0,
        sleeve_weights={"沪深300": 0.5},
    )
    assert bundle.excel_path.exists()
    assert bundle.html_path.exists()

    with ZipFile(bundle.excel_path) as z:
        names = z.namelist()
    assert "xl/workbook.xml" in names
    assert sum(1 for n in names if n.startswith("xl/worksheets/sheet")) == 4

    html = bundle.html_path.read_text(encoding="utf-8")
    assert "510300.SH" in html
    assert "<table>" in html


def test_backtest_report_includes_attribution(tmp_path: Path) -> None:
    metrics = PerformanceMetrics(0.4, 0.06, 0.14, 0.43, -0.26, 0.23, 0.50, 0.108)
    bench = PerformanceMetrics(0.41, 0.044, 0.193, 0.23, -0.41, 0.10, 0.49, 0.0)
    backtest = BroadIndexBacktest(
        curve=[
            CurvePoint(date(2024, 1, 2), 1_000_000.0, 0.0, 0.0),
            CurvePoint(date(2024, 1, 3), 1_010_000.0, 0.01, 0.0),
            CurvePoint(date(2024, 1, 4), 990_000.0, -0.0198, -0.0198),
        ],
        metrics=metrics,
        rebalances=[
            RebalanceEvent(
                trade_date=date(2024, 1, 2),
                nav_before=1_000_000.0,
                turnover_pct=0.5,
                cost_cny=150.0,
                target_weights={"510300.SH": 0.5},
                realized_weights_after={"510300.SH": 0.5},
                triggered_codes=["510300.SH"],
                sleeve_by_code={"510300.SH": "沪深300"},
                turnover_per_sleeve={"沪深300": 0.5},
            )
        ],
        benchmark_curve=[],
        benchmark_metrics=bench,
        daily_sleeve_attribution=[
            {"沪深300": 0.0},
            {"沪深300": 0.01},
            {"沪深300": -0.02},
        ],
        daily_sleeve_weights=[
            {"沪深300": 0.5},
            {"沪深300": 0.5},
            {"沪深300": 0.5},
        ],
    )
    bundle = write_backtest_report(
        output_dir=tmp_path,
        config_summary={"project": "test"},
        analysis=_empty_analysis(),
        backtest=backtest,
        sleeve_weights={"沪深300": 0.5},
    )
    assert bundle.excel_path.exists()
    assert bundle.html_path.exists()
    html = bundle.html_path.read_text(encoding="utf-8")
    assert "Attribution" in html
    assert "沪深300" in html
    assert "NAV curve" in html
