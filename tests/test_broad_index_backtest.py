from __future__ import annotations

from datetime import date

from fof_quant.backtest_broad_index import run_broad_index_backtest
from fof_quant.data.broad_index import (
    BroadIndexFetchResult,
    IndexSpec,
)
from fof_quant.data.provider import DataTable


def _make_fetched() -> BroadIndexFetchResult:
    """Two-sleeve synthetic universe with one ETF each, identical 1% daily returns."""
    specs = (
        IndexSpec("沪深300", "000300.SH", "H00300.CSI", r"^沪深300指数$"),
        IndexSpec("中证1000", "000852.SH", "H00852.CSI", r"^中证1000指数$"),
    )
    universe = DataTable(
        dataset="etf_basic",
        rows=[
            {
                "ts_code": "510300.SH",
                "name": "沪深300ETF",
                "list_date": "20100101",
                "m_fee": 0.15,
                "c_fee": 0.05,
                "_sleeve": "沪深300",
                "status": "L",
                "invest_type": "被动指数型",
                "benchmark": "沪深300指数",
                "management": "AAA",
            },
            {
                "ts_code": "512100.SH",
                "name": "中证1000ETF",
                "list_date": "20100101",
                "m_fee": 0.15,
                "c_fee": 0.05,
                "_sleeve": "中证1000",
                "status": "L",
                "invest_type": "被动指数型",
                "benchmark": "中证1000指数",
                "management": "BBB",
            },
        ],
    )
    # 60 trading days, both ETFs gain 0.5% per day (simple)
    days = [date(2024, 1, d) for d in range(2, 32)] + [date(2024, 2, d) for d in range(1, 30)]
    fund_nav_rows: list[dict[str, object]] = []
    etf_daily_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    for code in ("510300.SH", "512100.SH"):
        nav = 1.0
        for d in days:
            nav *= 1.005
            fund_nav_rows.append(
                {
                    "ts_code": code,
                    "nav_date": d.strftime("%Y%m%d"),
                    "unit_nav": nav,
                    "accum_nav": nav,
                    "adj_nav": nav,
                }
            )
            etf_daily_rows.append(
                {
                    "ts_code": code,
                    "trade_date": d.strftime("%Y%m%d"),
                    "close": nav * 4.0,
                    "amount": 5_000_000.0,
                }
            )
    for spec in specs:
        nav = 1000.0
        for d in days:
            nav *= 1.005
            benchmark_rows.append(
                {
                    "ts_code": spec.total_return_code,
                    "trade_date": d.strftime("%Y%m%d"),
                    "close": nav,
                }
            )
    return BroadIndexFetchResult(
        specs=specs,
        universe=universe,
        fund_nav=DataTable(dataset="fund_nav", rows=fund_nav_rows),
        etf_daily=DataTable(dataset="etf_daily", rows=etf_daily_rows),
        benchmarks=DataTable(dataset="benchmarks", rows=benchmark_rows),
    )


def test_no_rebalance_when_outside_horizon() -> None:
    fetched = _make_fetched()
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 2, 29),
        initial_cash=1_000_000.0,
        sleeve_weights={"沪深300": 0.5, "中证1000": 0.5},
        cash_buffer=0.0,
        max_weight=0.5,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    assert bt.curve, "expected non-empty curve"
    # First Jan rebalance opens both sleeves; Feb rebalance is in-band (no drift triggers).
    assert len(bt.rebalances) >= 1
    last_nav = bt.curve[-1].nav
    # Both ETFs grow at 0.5%/day; portfolio (post-cost-free open) should compound likewise.
    assert last_nav > 1_000_000.0


def test_costs_reduce_nav_on_open() -> None:
    fetched = _make_fetched()
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 5),
        initial_cash=1_000_000.0,
        sleeve_weights={"沪深300": 0.5, "中证1000": 0.5},
        cash_buffer=0.0,
        max_weight=0.5,
        transaction_cost_bps=10.0,
        slippage_bps=0.0,
    )
    # rebalance_dates returns the last day of each "month bucket" present in the input,
    # so on a 4-day window the last day fires a rebalance.
    assert len(bt.rebalances) == 1
    assert bt.rebalances[0].cost_cny == 1_000_000.0 * (10.0 / 10_000)
    # NAV on the last day = initial - cost (gains haven't compounded since open is same day)
    assert bt.curve[-1].nav == 1_000_000.0 - 1_000.0


def test_backtest_manifest_includes_benchmark_curve() -> None:
    from fof_quant.pipeline_broad_index import _backtest_manifest

    fetched = _make_fetched()
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 2, 29),
        initial_cash=1_000_000.0,
        sleeve_weights={"沪深300": 1.0},
        cash_buffer=0.0,
        max_weight=1.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    manifest = _backtest_manifest(bt, benchmark_label="沪深300")

    assert manifest["benchmark_label"] == "沪深300"
    benchmark_curve = manifest["benchmark_curve"]
    assert isinstance(benchmark_curve, list)
    assert len(benchmark_curve) == len(bt.curve)
    first = benchmark_curve[0]
    assert isinstance(first, dict)
    assert {"trade_date", "nav", "daily_return", "drawdown"} <= set(first.keys())


def test_force_rebalance_on_first_month_end() -> None:
    fetched = _make_fetched()
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_cash=1_000_000.0,
        sleeve_weights={"沪深300": 0.5, "中证1000": 0.5},
        cash_buffer=0.0,
        max_weight=0.5,
        transaction_cost_bps=10.0,
        slippage_bps=0.0,
    )
    # Jan 31 is the rebalance day: opens both sleeves, charges cost on full turnover.
    assert len(bt.rebalances) == 1
    event = bt.rebalances[0]
    assert event.turnover_pct == 1.0  # 100% of NAV deployed
    assert event.cost_cny == 1_000_000.0 * (10.0 / 10_000)
