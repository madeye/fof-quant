from datetime import date

import pytest

from fof_quant.allocation.engine import AllocationPlan, AllocationRow
from fof_quant.backtest.engine import BacktestEngine, PricePoint


def test_backtest_engine_builds_nav_curve_and_metrics() -> None:
    allocation = AllocationPlan(
        holdings=[AllocationRow("510300.SH", 0.9, 1.0, "selected")],
        cash_weight=0.1,
        constraint_checks={},
    )
    prices = [
        PricePoint(date(2024, 1, 2), "510300.SH", 10.0),
        PricePoint(date(2024, 1, 3), "510300.SH", 11.0),
        PricePoint(date(2024, 1, 4), "510300.SH", 9.0),
    ]

    result = BacktestEngine(
        initial_cash=1_000_000,
        transaction_cost_bps=0,
        slippage_bps=0,
    ).run(prices, allocation)

    assert [point.nav for point in result.curve] == pytest.approx([1.0, 1.09, 0.91])
    assert result.metrics.total_return == pytest.approx(-0.09)
    assert result.metrics.max_drawdown == pytest.approx(0.91 / 1.09 - 1.0)
    assert result.turnover == pytest.approx(0.9)


def test_backtest_engine_applies_trade_costs() -> None:
    allocation = AllocationPlan(
        holdings=[AllocationRow("510300.SH", 1.0, 1.0, "selected")],
        cash_weight=0.0,
        constraint_checks={},
    )
    prices = [PricePoint(date(2024, 1, 2), "510300.SH", 10.0)]

    result = BacktestEngine(
        initial_cash=1_000_000,
        transaction_cost_bps=10,
        slippage_bps=0,
    ).run(prices, allocation)

    assert result.curve[0].nav == pytest.approx(0.999)
