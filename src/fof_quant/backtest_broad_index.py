from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from fof_quant.analysis.broad_index import (
    BroadIndexAnalysis,
)
from fof_quant.analysis.broad_index import (
    analyze as analyze_broad_index,
)
from fof_quant.analysis.broad_index_allocation import (
    DEFAULT_SLEEVE_WEIGHTS,
    build_target_plan,
)
from fof_quant.backtest.metrics import PerformanceMetrics, calculate_metrics
from fof_quant.backtest.schedule import rebalance_dates
from fof_quant.data.broad_index import BroadIndexFetchResult


@dataclass(frozen=True)
class CurvePoint:
    trade_date: date
    nav: float
    daily_return: float
    drawdown: float


@dataclass(frozen=True)
class RebalanceEvent:
    trade_date: date
    nav_before: float
    turnover_pct: float
    cost_cny: float
    target_weights: dict[str, float]
    realized_weights_after: dict[str, float]
    triggered_codes: list[str]
    sleeve_by_code: dict[str, str] = field(default_factory=dict)
    turnover_per_sleeve: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BroadIndexBacktest:
    curve: list[CurvePoint]
    metrics: PerformanceMetrics
    rebalances: list[RebalanceEvent] = field(default_factory=list)
    benchmark_curve: list[CurvePoint] = field(default_factory=list)
    benchmark_metrics: PerformanceMetrics | None = None
    daily_sleeve_attribution: list[dict[str, float]] = field(default_factory=list)
    daily_sleeve_weights: list[dict[str, float]] = field(default_factory=list)


def run_broad_index_backtest(
    fetched: BroadIndexFetchResult,
    *,
    start_date: date,
    end_date: date,
    initial_cash: float,
    sleeve_weights: dict[str, float] | None = None,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
    abs_band_pp: float = 1.0,
    rel_band_pct: float = 25.0,
    transaction_cost_bps: float = 2.0,
    slippage_bps: float = 1.0,
    rebalance_frequency: str = "monthly",
    benchmark_label: str = "沪深300",
    semiannual_force_months: tuple[int, int] = (1, 7),
    pit_analysis_provider: Callable[[date], BroadIndexAnalysis | None] | None = None,
) -> BroadIndexBacktest:
    weights = sleeve_weights or DEFAULT_SLEEVE_WEIGHTS
    cost_rate = (transaction_cost_bps + slippage_bps) / 10_000

    nav_by_code, fund_listing = _index_nav_by_code(fetched)
    benchmark_nav_series = _benchmark_series(fetched, benchmark_label)
    trading_days = _trading_days(fetched, start_date, end_date)
    if not trading_days:
        empty = PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0)
        return BroadIndexBacktest(curve=[], metrics=empty, rebalances=[])
    rebal_days = set(rebalance_dates(trading_days, rebalance_frequency))  # type: ignore[arg-type]

    holdings_value: dict[str, float] = {}
    cash = initial_cash
    portfolio_nav = initial_cash
    peak = initial_cash
    curve: list[CurvePoint] = []
    rebalances: list[RebalanceEvent] = []
    prev_nav_by_code: dict[str, float] = {}
    pit_universe = list(fetched.universe.rows)
    current_sleeve_by_code: dict[str, str] = {}
    daily_sleeve_attribution: list[dict[str, float]] = []
    daily_sleeve_weights: list[dict[str, float]] = []

    for d in trading_days:
        # Snapshot weights at start-of-day (before MTM moves them) for attribution
        sod_weights_per_code: dict[str, float] = (
            {code: v / portfolio_nav for code, v in holdings_value.items()}
            if portfolio_nav > 0
            else {}
        )

        # MTM: scale each holding by its adj_nav daily return; track per-code daily return
        per_code_return: dict[str, float] = {}
        for code in list(holdings_value):
            today = nav_by_code.get(code, {}).get(d)
            yesterday = prev_nav_by_code.get(code)
            if today is not None and yesterday is not None and yesterday > 0:
                ret = today / yesterday - 1.0
                holdings_value[code] *= 1.0 + ret
                per_code_return[code] = ret
            elif today is None:
                per_code_return[code] = 0.0
        portfolio_nav = sum(holdings_value.values()) + cash
        # Update prev NAV ledger for codes we touched today
        for code in nav_by_code:
            today = nav_by_code[code].get(d)
            if today is not None:
                prev_nav_by_code[code] = today

        # Per-sleeve attribution for this day = sum_{c in sleeve} weight_sod_c * return_c
        sleeve_attribution_today: dict[str, float] = {}
        for code, w in sod_weights_per_code.items():
            sleeve = current_sleeve_by_code.get(code, "未分类")
            sleeve_attribution_today[sleeve] = (
                sleeve_attribution_today.get(sleeve, 0.0) + w * per_code_return.get(code, 0.0)
            )

        if d in rebal_days:
            month_force = d.month in semiannual_force_months and _is_first_rebal_in_month(
                d, rebal_days
            )
            pit_analysis = (
                pit_analysis_provider(d) if pit_analysis_provider is not None else None
            )
            if pit_analysis is None:
                pit_analysis = _default_pit_analysis(fetched, pit_universe, d)
            current_sleeve_by_code.update(_sleeve_by_code_from_analysis(pit_analysis))
            event = _rebalance(
                d=d,
                pit_analysis=pit_analysis,
                weights=weights,
                cash_buffer=cash_buffer,
                max_weight=max_weight,
                abs_band_pp=abs_band_pp,
                rel_band_pct=rel_band_pct,
                holdings_value=holdings_value,
                portfolio_nav=portfolio_nav,
                cost_rate=cost_rate,
                force=month_force,
                sleeve_by_code=current_sleeve_by_code,
            )
            if event is not None:
                rebalances.append(event)
                portfolio_nav -= event.cost_cny
                cash = portfolio_nav - sum(holdings_value.values())

        prev_nav = curve[-1].nav if curve else initial_cash
        daily_return = portfolio_nav / prev_nav - 1.0 if curve else 0.0
        peak = max(peak, portfolio_nav)
        drawdown = portfolio_nav / peak - 1.0
        curve.append(CurvePoint(d, portfolio_nav, daily_return, drawdown))
        eod_sleeve_weights: dict[str, float] = {}
        if portfolio_nav > 0:
            for code, v in holdings_value.items():
                sleeve = current_sleeve_by_code.get(code, "未分类")
                eod_sleeve_weights[sleeve] = eod_sleeve_weights.get(sleeve, 0.0) + v / portfolio_nav
        daily_sleeve_attribution.append(sleeve_attribution_today)
        daily_sleeve_weights.append(eod_sleeve_weights)

    benchmark_returns = _benchmark_returns(benchmark_nav_series, [pt.trade_date for pt in curve])
    metrics = calculate_metrics(curve, benchmark_returns)
    bench_curve = _benchmark_curve(benchmark_nav_series, [pt.trade_date for pt in curve])
    bench_metrics = calculate_metrics(bench_curve)
    _ = fund_listing  # keep handle in case we later filter ineligibles
    return BroadIndexBacktest(
        curve=curve,
        metrics=metrics,
        rebalances=rebalances,
        benchmark_curve=bench_curve,
        benchmark_metrics=bench_metrics,
        daily_sleeve_attribution=daily_sleeve_attribution,
        daily_sleeve_weights=daily_sleeve_weights,
    )


# ----- internals -----


def _default_pit_analysis(
    fetched: BroadIndexFetchResult,
    pit_universe: list[dict[str, Any]],
    d: date,
) -> BroadIndexAnalysis:
    pit_fetched = _slice_pit(fetched, pit_universe, d)
    return analyze_broad_index(pit_fetched, as_of=d)


def _sleeve_by_code_from_analysis(analysis: BroadIndexAnalysis) -> dict[str, str]:
    out: dict[str, str] = {}
    for sp in analysis.sleeve_picks:
        if sp.pick is not None:
            out[sp.pick.ts_code] = sp.spec.label
        for runner in sp.runners_up:
            out.setdefault(runner.ts_code, sp.spec.label)
    return out


def _rebalance(
    *,
    d: date,
    pit_analysis: BroadIndexAnalysis,
    weights: dict[str, float],
    cash_buffer: float,
    max_weight: float,
    abs_band_pp: float,
    rel_band_pct: float,
    holdings_value: dict[str, float],
    portfolio_nav: float,
    cost_rate: float,
    force: bool,
    sleeve_by_code: dict[str, str],
) -> RebalanceEvent | None:
    target_plan = build_target_plan(
        pit_analysis,
        sleeve_weights=weights,
        cash_buffer=cash_buffer,
        max_weight=max_weight,
    )
    target_by_code = {row.etf_code: row.weight for row in target_plan.holdings}
    if portfolio_nav <= 0:
        return None
    current_weights = {code: v / portfolio_nav for code, v in holdings_value.items()}

    triggered: list[str] = []
    target_value: dict[str, float] = {}
    for code in sorted(set(target_by_code) | set(current_weights)):
        tgt = target_by_code.get(code, 0.0)
        cur = current_weights.get(code, 0.0)
        drift_pp = (cur - tgt) * 100.0
        rel_pp = drift_pp / (tgt * 100.0) * 100.0 if tgt > 0 else float("inf")
        opening_or_closing = (tgt > 0 and cur == 0.0) or (tgt == 0.0 and cur > 0)
        triggers = (
            force
            or opening_or_closing
            or abs(drift_pp) > abs_band_pp
            or (tgt > 0 and abs(rel_pp) > rel_band_pct)
        )
        if triggers:
            triggered.append(code)
            target_value[code] = tgt * portfolio_nav

    if not triggered:
        return None

    turnover_cny = 0.0
    turnover_per_sleeve_cny: dict[str, float] = {}
    for code in triggered:
        new_value = target_value.get(code, 0.0)
        delta = new_value - holdings_value.get(code, 0.0)
        turnover_cny += abs(delta)
        sleeve = sleeve_by_code.get(code, "未分类")
        turnover_per_sleeve_cny[sleeve] = (
            turnover_per_sleeve_cny.get(sleeve, 0.0) + abs(delta)
        )
        if new_value > 0:
            holdings_value[code] = new_value
        else:
            holdings_value.pop(code, None)
    cost = turnover_cny * cost_rate
    new_nav = portfolio_nav - cost
    realized = {code: v / new_nav for code, v in holdings_value.items()} if new_nav else {}
    return RebalanceEvent(
        trade_date=d,
        nav_before=portfolio_nav,
        turnover_pct=turnover_cny / portfolio_nav,
        cost_cny=cost,
        target_weights=dict(target_by_code),
        realized_weights_after=realized,
        triggered_codes=triggered,
        sleeve_by_code=dict(sleeve_by_code),
        turnover_per_sleeve={s: v / portfolio_nav for s, v in turnover_per_sleeve_cny.items()},
    )


def _slice_pit(
    fetched: BroadIndexFetchResult,
    universe_rows: list[dict[str, Any]],
    d: date,
) -> BroadIndexFetchResult:
    """Return a BroadIndexFetchResult with all date-bearing rows restricted to <= d.
    Universe is sliced by list_date <= d."""
    cutoff = d.strftime("%Y%m%d")
    pit_universe = type(fetched.universe)(
        dataset=fetched.universe.dataset,
        rows=[r for r in universe_rows if str(r.get("list_date", "")) <= cutoff],
    )
    pit_nav = type(fetched.fund_nav)(
        dataset=fetched.fund_nav.dataset,
        rows=[r for r in fetched.fund_nav.rows if str(r["nav_date"]) <= cutoff],
    )
    pit_daily = type(fetched.etf_daily)(
        dataset=fetched.etf_daily.dataset,
        rows=[r for r in fetched.etf_daily.rows if str(r["trade_date"]) <= cutoff],
    )
    pit_bench = type(fetched.benchmarks)(
        dataset=fetched.benchmarks.dataset,
        rows=[r for r in fetched.benchmarks.rows if str(r["trade_date"]) <= cutoff],
    )
    return type(fetched)(
        specs=fetched.specs,
        universe=pit_universe,
        fund_nav=pit_nav,
        etf_daily=pit_daily,
        benchmarks=pit_bench,
    )


def _index_nav_by_code(
    fetched: BroadIndexFetchResult,
) -> tuple[dict[str, dict[date, float]], dict[str, date]]:
    nav: dict[str, dict[date, float]] = {}
    listing: dict[str, date] = {}
    for row in fetched.fund_nav.rows:
        adj = row.get("adj_nav")
        if adj is None:
            continue
        code = str(row["ts_code"])
        nav.setdefault(code, {})[_parse_date(str(row["nav_date"]))] = float(adj)
    for row in fetched.universe.rows:
        listing[str(row["ts_code"])] = _parse_date(str(row["list_date"]))
    return nav, listing


def _benchmark_series(
    fetched: BroadIndexFetchResult,
    benchmark_label: str,
) -> dict[date, float]:
    spec = next((s for s in fetched.specs if s.label == benchmark_label), None)
    if spec is None:
        return {}
    out: dict[date, float] = {}
    for row in fetched.benchmarks.rows:
        if str(row["ts_code"]) != spec.total_return_code:
            continue
        out[_parse_date(str(row["trade_date"]))] = float(row["close"])
    return out


def _trading_days(
    fetched: BroadIndexFetchResult,
    start_date: date,
    end_date: date,
) -> list[date]:
    days = {
        _parse_date(str(row["trade_date"]))
        for row in fetched.benchmarks.rows
        if start_date <= _parse_date(str(row["trade_date"])) <= end_date
    }
    return sorted(days)


def _benchmark_returns(series: dict[date, float], days: list[date]) -> list[float]:
    out: list[float] = []
    prev: float | None = None
    for d in days:
        v = series.get(d)
        if prev is not None and prev > 0 and v is not None:
            out.append(v / prev - 1.0)
        elif prev is not None:
            out.append(0.0)
        if v is not None:
            prev = v
    return out


def _benchmark_curve(series: dict[date, float], days: list[date]) -> list[CurvePoint]:
    if not days or not series:
        return []
    base = next((series[d] for d in days if d in series), None)
    if base is None or base <= 0:
        return []
    curve: list[CurvePoint] = []
    peak = base
    prev = base
    for d in days:
        v = series.get(d, prev)
        ret = v / prev - 1.0 if curve else 0.0
        peak = max(peak, v)
        dd = v / peak - 1.0
        curve.append(CurvePoint(d, v / base, ret, dd))
        prev = v
    return curve


def _is_first_rebal_in_month(d: date, rebal_days: set[date]) -> bool:
    return not any(rd.year == d.year and rd.month == d.month and rd < d for rd in rebal_days)


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def precompute_pit_cache(
    fetched: BroadIndexFetchResult,
    *,
    start_date: date,
    end_date: date,
    rebalance_frequency: str = "monthly",
) -> dict[date, BroadIndexAnalysis]:
    """Compute the PIT BroadIndexAnalysis for every rebalance date once.
    Sweeps that vary scheme/band but share the same data window can pass the
    result back as `pit_analysis_provider=cache.__getitem__`."""
    days = _trading_days(fetched, start_date, end_date)
    if not days:
        return {}
    rebal_days = rebalance_dates(days, rebalance_frequency)  # type: ignore[arg-type]
    pit_universe = list(fetched.universe.rows)
    return {d: _default_pit_analysis(fetched, pit_universe, d) for d in rebal_days}


__all__ = [
    "BroadIndexBacktest",
    "CurvePoint",
    "RebalanceEvent",
    "precompute_pit_cache",
    "run_broad_index_backtest",
]
