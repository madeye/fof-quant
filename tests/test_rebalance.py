from __future__ import annotations

import json
from pathlib import Path

from fof_quant.allocation.engine import AllocationPlan, AllocationRow
from fof_quant.portfolio.holdings import CurrentPortfolio, load_holdings
from fof_quant.portfolio.rebalance import compute_rebalance


def _plan(rows: list[tuple[str, float]]) -> AllocationPlan:
    return AllocationPlan(
        holdings=[AllocationRow(etf_code=c, weight=w, score=0.0, reason="") for c, w in rows],
        cash_weight=1.0 - sum(w for _, w in rows),
        constraint_checks={},
    )


def test_band_holds_within_tolerance() -> None:
    plan = _plan([("510300.SH", 0.35), ("512100.SH", 0.20)])
    sleeve_by_code = {"510300.SH": "沪深300", "512100.SH": "中证1000"}
    current_weights = {"510300.SH": 0.37, "512100.SH": 0.18}
    last_price = {"510300.SH": 4.0, "512100.SH": 1.5}
    lines = compute_rebalance(
        plan,
        sleeve_by_code=sleeve_by_code,
        current_weights=current_weights,
        last_price=last_price,
        total_aum_cny=1_000_000.0,
        abs_band_pp=5.0,
        rel_band_pct=25.0,
    )
    actions = {line.ts_code: line.action for line in lines}
    assert actions["510300.SH"] == "hold"
    assert actions["512100.SH"] == "hold"
    assert all(line.delta_shares_lot100 == 0 for line in lines)


def test_band_triggers_buy_on_open() -> None:
    plan = _plan([("510300.SH", 0.35)])
    lines = compute_rebalance(
        plan,
        sleeve_by_code={"510300.SH": "沪深300"},
        current_weights={},  # all cash
        last_price={"510300.SH": 4.0},
        total_aum_cny=1_000_000.0,
    )
    assert len(lines) == 1
    line = lines[0]
    assert line.action == "open"
    assert line.target_notional_cny == 350_000.0
    assert line.delta_shares_lot100 == int(350_000.0 / 4.0 // 100) * 100  # 87_500


def test_band_triggers_sell_on_overweight() -> None:
    plan = _plan([("510300.SH", 0.35)])
    lines = compute_rebalance(
        plan,
        sleeve_by_code={"510300.SH": "沪深300"},
        current_weights={"510300.SH": 0.45},
        last_price={"510300.SH": 4.0},
        total_aum_cny=1_000_000.0,
        abs_band_pp=5.0,
    )
    line = lines[0]
    assert line.action == "sell"
    assert line.delta_notional_cny == -100_000.0
    assert line.delta_shares_lot100 == -25_000


def test_relative_band_catches_small_target_drift() -> None:
    # 6% target with 30% relative drift = 1.8pp absolute < 5pp band, but rel > 25%
    plan = _plan([("510300.SH", 0.06)])
    lines = compute_rebalance(
        plan,
        sleeve_by_code={"510300.SH": "沪深300"},
        current_weights={"510300.SH": 0.078},
        last_price={"510300.SH": 4.0},
        total_aum_cny=1_000_000.0,
        abs_band_pp=5.0,
        rel_band_pct=25.0,
    )
    assert lines[0].action == "sell"


def test_close_when_target_zero() -> None:
    plan = _plan([("510300.SH", 0.35)])
    lines = compute_rebalance(
        plan,
        sleeve_by_code={"510300.SH": "沪深300", "510500.SH": "中证500"},
        current_weights={"510300.SH": 0.30, "510500.SH": 0.20},
        last_price={"510300.SH": 4.0, "510500.SH": 8.0},
        total_aum_cny=1_000_000.0,
    )
    by_code = {line.ts_code: line for line in lines}
    assert by_code["510500.SH"].action == "close"
    assert by_code["510500.SH"].target_weight == 0.0


def test_force_rebalances_even_within_band() -> None:
    plan = _plan([("510300.SH", 0.35)])
    lines = compute_rebalance(
        plan,
        sleeve_by_code={"510300.SH": "沪深300"},
        current_weights={"510300.SH": 0.36},
        last_price={"510300.SH": 4.0},
        total_aum_cny=1_000_000.0,
        force=True,
    )
    assert lines[0].action == "sell"


def test_load_holdings_round_trip(tmp_path: Path) -> None:
    payload = {
        "as_of": "2026-04-25",
        "cash_cny": 50_000,
        "positions": [
            {"ts_code": "510300.SH", "shares": 100_000},
            {"ts_code": "510500.SH", "shares": 25_000},
        ],
    }
    path = tmp_path / "holdings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    portfolio = load_holdings(path)
    assert portfolio.cash_cny == 50_000.0
    assert len(portfolio.positions) == 2
    last_price = {"510300.SH": 4.0, "510500.SH": 8.0}
    assert portfolio.total_aum(last_price) == 50_000 + 100_000 * 4.0 + 25_000 * 8.0
    weights = portfolio.weights(last_price)
    assert sum(weights.values()) + portfolio.cash_cny / portfolio.total_aum(last_price) == 1.0


def test_empty_portfolio_starts_all_cash() -> None:
    from datetime import date as _d

    p = CurrentPortfolio.empty(as_of=_d(2026, 4, 25), cash_cny=1_000_000.0)
    assert p.total_aum({}) == 1_000_000.0
    assert p.weights({}) == {}
