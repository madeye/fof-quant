"""Integration tests for regime-switched broad-index backtest."""
from __future__ import annotations

from datetime import date

import pytest

from fof_quant.backtest_broad_index import run_broad_index_backtest
from fof_quant.data.broad_index import BroadIndexFetchResult, IndexSpec
from fof_quant.data.provider import DataTable
from fof_quant.portfolio.regime import Regime


def _make_fetched() -> BroadIndexFetchResult:
    """Same two-sleeve synthetic fixture as test_broad_index_backtest."""
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
    days = [date(2024, 1, d) for d in range(2, 32)] + [date(2024, 2, d) for d in range(1, 30)]
    fund_nav_rows: list[dict[str, object]] = []
    etf_daily_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    for code in ("510300.SH", "512100.SH"):
        nav = 1.0
        for d in days:
            nav *= 1.005
            fund_nav_rows.append(
                {"ts_code": code, "nav_date": d.strftime("%Y%m%d"),
                 "unit_nav": nav, "accum_nav": nav, "adj_nav": nav}
            )
            etf_daily_rows.append(
                {"ts_code": code, "trade_date": d.strftime("%Y%m%d"),
                 "close": nav * 4.0, "amount": 5_000_000.0}
            )
    for spec in specs:
        nav = 1000.0
        for d in days:
            nav *= 1.005
            benchmark_rows.append(
                {"ts_code": spec.total_return_code,
                 "trade_date": d.strftime("%Y%m%d"), "close": nav}
            )
    return BroadIndexFetchResult(
        specs=specs,
        universe=universe,
        fund_nav=DataTable(dataset="fund_nav", rows=fund_nav_rows),
        etf_daily=DataTable(dataset="etf_daily", rows=etf_daily_rows),
        benchmarks=DataTable(dataset="benchmarks", rows=benchmark_rows),
    )


class _ConstantRegime:
    """Test double — always returns the same regime."""

    def __init__(self, regime: Regime) -> None:
        self._regime = regime

    def signal_for_date(self, d: date) -> Regime:  # noqa: ARG002
        return self._regime


def test_regime_provider_requires_both_sleeve_maps() -> None:
    fetched = _make_fetched()
    with pytest.raises(ValueError, match="bull_sleeve_weights and bear_sleeve_weights"):
        run_broad_index_backtest(
            fetched,
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 31),
            initial_cash=1_000_000.0,
            sleeve_weights=None,
            cash_buffer=0.0,
            max_weight=1.0,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
            regime_provider=_ConstantRegime("bull"),
            bull_sleeve_weights=None,
            bear_sleeve_weights={"沪深300": 1.0},
        )


def test_constant_bull_regime_uses_bull_sleeve_weights() -> None:
    fetched = _make_fetched()
    bull_weights = {"沪深300": 1.0}  # 100% sleeve A
    bear_weights = {"中证1000": 1.0}  # 100% sleeve B
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_cash=1_000_000.0,
        cash_buffer=0.0,
        max_weight=1.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        regime_provider=_ConstantRegime("bull"),
        bull_sleeve_weights=bull_weights,
        bear_sleeve_weights=bear_weights,
    )
    # Single rebalance on Jan 31 (forced first-month) — should target bull only.
    assert len(bt.rebalances) == 1
    targets = bt.rebalances[0].target_weights
    assert "510300.SH" in targets and targets["510300.SH"] == pytest.approx(1.0)
    assert all(code != "512100.SH" or w == 0 for code, w in targets.items())


def test_constant_bear_regime_uses_bear_sleeve_weights() -> None:
    fetched = _make_fetched()
    bull_weights = {"沪深300": 1.0}
    bear_weights = {"中证1000": 1.0}
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_cash=1_000_000.0,
        cash_buffer=0.0,
        max_weight=1.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        regime_provider=_ConstantRegime("bear"),
        bull_sleeve_weights=bull_weights,
        bear_sleeve_weights=bear_weights,
    )
    assert len(bt.rebalances) == 1
    targets = bt.rebalances[0].target_weights
    assert "512100.SH" in targets and targets["512100.SH"] == pytest.approx(1.0)


def test_regime_flip_drives_sleeve_switch() -> None:
    """A regime that flips bull→bear between the two month-end rebalances should
    trigger a turnover from bull to bear sleeve on the second rebalance."""
    fetched = _make_fetched()

    class _FlipAfter:
        def __init__(self, cutoff: date) -> None:
            self._cutoff = cutoff

        def signal_for_date(self, d: date) -> Regime:
            return "bull" if d <= self._cutoff else "bear"

    bull_weights = {"沪深300": 1.0}
    bear_weights = {"中证1000": 1.0}
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 2, 29),
        initial_cash=1_000_000.0,
        cash_buffer=0.0,
        max_weight=1.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        regime_provider=_FlipAfter(cutoff=date(2024, 1, 31)),
        bull_sleeve_weights=bull_weights,
        bear_sleeve_weights=bear_weights,
    )
    # Two month-end rebalances; first targets bull (510300), second targets bear (512100)
    assert len(bt.rebalances) == 2
    first, second = bt.rebalances
    assert first.target_weights.get("510300.SH") == pytest.approx(1.0)
    assert second.target_weights.get("512100.SH") == pytest.approx(1.0)
    # Second rebalance should incur full turnover (sold 510300, bought 512100)
    assert second.turnover_pct == pytest.approx(2.0, abs=0.05)


def test_no_regime_falls_back_to_static_sleeve_weights() -> None:
    """When regime_provider is None, the engine ignores bull/bear maps and
    uses the static sleeve_weights as before — i.e. backwards compatible."""
    fetched = _make_fetched()
    bt = run_broad_index_backtest(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_cash=1_000_000.0,
        sleeve_weights={"沪深300": 0.5, "中证1000": 0.5},
        cash_buffer=0.0,
        max_weight=0.5,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
        regime_provider=None,
        # These should be ignored when regime_provider is None
        bull_sleeve_weights={"沪深300": 1.0},
        bear_sleeve_weights={"中证1000": 1.0},
    )
    assert len(bt.rebalances) == 1
    targets = bt.rebalances[0].target_weights
    # Static 50/50 split, not the bull-only 100% override
    assert targets.get("510300.SH") == pytest.approx(0.5)
    assert targets.get("512100.SH") == pytest.approx(0.5)
