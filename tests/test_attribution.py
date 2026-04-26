from __future__ import annotations

from datetime import date

from fof_quant.analysis.attribution import (
    compute_attribution,
    render_attribution_table,
    render_attribution_top_drawdown,
)
from fof_quant.backtest.metrics import PerformanceMetrics
from fof_quant.backtest_broad_index import (
    BroadIndexBacktest,
    CurvePoint,
    RebalanceEvent,
)


def _empty_metrics() -> PerformanceMetrics:
    return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)


def test_attribution_handles_empty_backtest() -> None:
    bt = BroadIndexBacktest(curve=[], metrics=_empty_metrics())
    summary = compute_attribution(bt)
    assert summary.sleeves == []
    assert summary.portfolio_total_return_pct == 0.0
    assert "no attribution" in render_attribution_table(summary)


def test_attribution_sums_per_sleeve_contribution() -> None:
    # Two days, two sleeves; portfolio is 60% A, 40% B both days.
    # Day 1: A=+1%, B=-2%. contrib_A=0.60*0.01=+0.006; contrib_B=0.40*-0.02=-0.008
    # Day 2: A=+0%, B=+5%. contrib_A=0.60*0.00=+0;     contrib_B=0.40*0.05=+0.020
    # Totals: A=+0.006, B=+0.012. Sum=+0.018 (1.80%).
    daily_attribution = [
        {"A": 0.006, "B": -0.008},
        {"A": 0.0, "B": 0.020},
    ]
    daily_weights = [
        {"A": 0.60, "B": 0.40},
        {"A": 0.60, "B": 0.40},
    ]
    curve = [
        CurvePoint(date(2024, 1, 2), 998_000.0, -0.002, -0.002),
        CurvePoint(date(2024, 1, 3), 1_018_000.0, 0.020, 0.0),
    ]
    bt = BroadIndexBacktest(
        curve=curve,
        metrics=_empty_metrics(),
        daily_sleeve_attribution=daily_attribution,
        daily_sleeve_weights=daily_weights,
    )
    summary = compute_attribution(bt)
    by_sleeve = {s.sleeve: s for s in summary.sleeves}
    assert abs(by_sleeve["A"].contribution_pct - 0.6) < 1e-9
    assert abs(by_sleeve["B"].contribution_pct - 1.2) < 1e-9
    assert abs(by_sleeve["A"].avg_weight_pct - 60.0) < 1e-9
    assert abs(by_sleeve["B"].avg_weight_pct - 40.0) < 1e-9
    assert by_sleeve["A"].days_held == 2
    # Sum of contributions ≈ 1.80% (arithmetic, not geometric)
    assert abs(summary.sum_of_sleeve_contributions_pct - 1.80) < 1e-9


def test_attribution_records_per_sleeve_turnover_and_cost() -> None:
    bt = BroadIndexBacktest(
        curve=[
            CurvePoint(date(2024, 1, 2), 1_000_000.0, 0.0, 0.0),
            CurvePoint(date(2024, 1, 3), 1_000_000.0, 0.0, 0.0),
        ],
        metrics=_empty_metrics(),
        daily_sleeve_attribution=[{"A": 0.0}, {"A": 0.0}],
        daily_sleeve_weights=[{"A": 0.5}, {"A": 0.5}],
        rebalances=[
            RebalanceEvent(
                trade_date=date(2024, 1, 2),
                nav_before=1_000_000.0,
                turnover_pct=1.0,
                cost_cny=300.0,
                target_weights={"a.SH": 0.5, "b.SH": 0.5},
                realized_weights_after={},
                triggered_codes=["a.SH", "b.SH"],
                sleeve_by_code={"a.SH": "A", "b.SH": "B"},
                turnover_per_sleeve={"A": 0.5, "B": 0.5},
            )
        ],
    )
    summary = compute_attribution(bt)
    by_sleeve = {s.sleeve: s for s in summary.sleeves}
    assert abs(by_sleeve["A"].turnover_pct - 50.0) < 1e-9
    assert abs(by_sleeve["A"].cost_cny - 150.0) < 1e-9
    assert by_sleeve["A"].rebalance_count == 1


def test_top_drawdown_picks_worst_days() -> None:
    bt = BroadIndexBacktest(
        curve=[
            CurvePoint(date(2024, 1, d), 1_000_000.0 + d, ret, 0.0)
            for d, ret in [(2, -0.01), (3, -0.03), (4, -0.005), (5, -0.02)]
        ],
        metrics=_empty_metrics(),
        daily_sleeve_attribution=[
            {"A": -0.005, "B": -0.005},
            {"A": -0.020, "B": -0.010},
            {"A": -0.003, "B": -0.002},
            {"A": -0.015, "B": -0.005},
        ],
        daily_sleeve_weights=[{"A": 0.5, "B": 0.5}] * 4,
    )
    text = render_attribution_top_drawdown(bt, top_n_days=2)
    # Worst day is Jan 3 (-3%); second worst is Jan 5 (-2%)
    assert "2024-01-03" in text
    assert "2024-01-05" in text
    # Best day shouldn't appear
    assert "2024-01-04" not in text
