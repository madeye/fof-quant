from __future__ import annotations

from dataclasses import dataclass

from fof_quant.backtest_broad_index import BroadIndexBacktest


@dataclass(frozen=True)
class SleeveAttribution:
    sleeve: str
    contribution_pct: float  # arithmetic sum of daily weight × return, in %
    avg_weight_pct: float  # time-weighted average end-of-day weight, in %
    days_held: int
    rebalance_count: int
    turnover_pct: float  # total turnover (sum of |delta_w|) attributable to this sleeve, in %
    cost_cny: float  # sleeve's share of cumulative cost
    contribution_per_unit_weight: float  # contribution_pct / avg_weight_pct (efficiency proxy)


@dataclass(frozen=True)
class AttributionSummary:
    sleeves: list[SleeveAttribution]
    portfolio_total_return_pct: float  # geometric, from curve (for residual reporting)
    sum_of_sleeve_contributions_pct: float  # arithmetic sum across sleeves
    geometric_arithmetic_residual_pct: float  # portfolio_total - sum_of_contributions


def compute_attribution(backtest: BroadIndexBacktest) -> AttributionSummary:
    sleeve_contribution: dict[str, float] = {}
    sleeve_weight_sum: dict[str, float] = {}
    sleeve_days_held: dict[str, int] = {}

    for daily in backtest.daily_sleeve_attribution:
        for sleeve, contribution in daily.items():
            sleeve_contribution[sleeve] = sleeve_contribution.get(sleeve, 0.0) + contribution
    for daily in backtest.daily_sleeve_weights:
        for sleeve, weight in daily.items():
            sleeve_weight_sum[sleeve] = sleeve_weight_sum.get(sleeve, 0.0) + weight
            if weight > 0:
                sleeve_days_held[sleeve] = sleeve_days_held.get(sleeve, 0) + 1

    sleeve_turnover: dict[str, float] = {}
    sleeve_rebal_count: dict[str, int] = {}
    sleeve_cost: dict[str, float] = {}
    total_turnover_for_cost = sum(r.turnover_pct for r in backtest.rebalances)
    for event in backtest.rebalances:
        for sleeve, t in event.turnover_per_sleeve.items():
            sleeve_turnover[sleeve] = sleeve_turnover.get(sleeve, 0.0) + t
            sleeve_rebal_count[sleeve] = sleeve_rebal_count.get(sleeve, 0) + 1
            if total_turnover_for_cost > 0:
                share = t / total_turnover_for_cost
                sleeve_cost[sleeve] = sleeve_cost.get(sleeve, 0.0) + share * event.cost_cny

    n_days = max(len(backtest.daily_sleeve_weights), 1)
    sleeves_seen = sorted(set(sleeve_contribution) | set(sleeve_weight_sum) | set(sleeve_turnover))
    rows: list[SleeveAttribution] = []
    for sleeve in sleeves_seen:
        contrib_pct = sleeve_contribution.get(sleeve, 0.0) * 100.0
        avg_w_pct = sleeve_weight_sum.get(sleeve, 0.0) / n_days * 100.0
        rows.append(
            SleeveAttribution(
                sleeve=sleeve,
                contribution_pct=contrib_pct,
                avg_weight_pct=avg_w_pct,
                days_held=sleeve_days_held.get(sleeve, 0),
                rebalance_count=sleeve_rebal_count.get(sleeve, 0),
                turnover_pct=sleeve_turnover.get(sleeve, 0.0) * 100.0,
                cost_cny=sleeve_cost.get(sleeve, 0.0),
                contribution_per_unit_weight=(
                    contrib_pct / avg_w_pct if avg_w_pct > 0 else 0.0
                ),
            )
        )
    rows.sort(key=lambda r: -r.contribution_pct)

    portfolio_total = (
        (backtest.curve[-1].nav / backtest.curve[0].nav - 1.0) * 100.0
        if backtest.curve
        else 0.0
    )
    sum_contrib = sum(r.contribution_pct for r in rows)
    return AttributionSummary(
        sleeves=rows,
        portfolio_total_return_pct=portfolio_total,
        sum_of_sleeve_contributions_pct=sum_contrib,
        geometric_arithmetic_residual_pct=portfolio_total - sum_contrib,
    )


def render_attribution_table(summary: AttributionSummary) -> str:
    if not summary.sleeves:
        return "(no attribution)"
    header = (
        f"{'sleeve':14s}  {'contrib%':>9s}  {'avg w%':>7s}  "
        f"{'eff':>5s}  {'days':>5s}  {'rebal':>5s}  {'turn%':>7s}  {'cost¥':>9s}"
    )
    rule = "-" * len(header)
    lines = [header, rule]
    for r in summary.sleeves:
        lines.append(
            f"{r.sleeve:14s}  {r.contribution_pct:9.2f}  {r.avg_weight_pct:7.2f}  "
            f"{r.contribution_per_unit_weight:5.2f}  {r.days_held:5d}  "
            f"{r.rebalance_count:5d}  {r.turnover_pct:7.1f}  {r.cost_cny:9,.0f}"
        )
    lines.append(rule)
    lines.append(
        f"  Σ sleeve contributions: {summary.sum_of_sleeve_contributions_pct:+.2f}%   "
        f"portfolio total (geometric): {summary.portfolio_total_return_pct:+.2f}%   "
        f"residual (geom-arith linking): {summary.geometric_arithmetic_residual_pct:+.2f}%"
    )
    return "\n".join(lines)


def render_attribution_top_drawdown(
    backtest: BroadIndexBacktest,
    top_n_days: int = 10,
) -> str:
    """Find the days with the largest negative portfolio returns and show
    which sleeves contributed most to the drawdown."""
    if not backtest.curve or not backtest.daily_sleeve_attribution:
        return "(no curve data)"
    indexed = list(zip(backtest.curve, backtest.daily_sleeve_attribution, strict=True))
    losers = sorted(indexed, key=lambda pair: pair[0].daily_return)[:top_n_days]
    lines: list[str] = [f"Top {top_n_days} drawdown days (sleeve contribution to that day):"]
    header = f"  {'date':>10s}  {'port%':>7s}    " + "    sleeves (contrib%)"
    lines.append(header)
    for cp, attrib in losers:
        items = sorted(attrib.items(), key=lambda kv: kv[1])
        biggest_drag = ", ".join(
            f"{sleeve}={contrib * 100:+.2f}" for sleeve, contrib in items[:3] if contrib < 0
        )
        lines.append(
            f"  {cp.trade_date.isoformat():>10s}  {cp.daily_return * 100:7.2f}    {biggest_drag}"
        )
    return "\n".join(lines)


def attribution_payload(summary: AttributionSummary) -> dict[str, object]:
    return {
        "sleeves": [
            {
                "sleeve": s.sleeve,
                "contribution_pct": s.contribution_pct,
                "avg_weight_pct": s.avg_weight_pct,
                "days_held": s.days_held,
                "rebalance_count": s.rebalance_count,
                "turnover_pct": s.turnover_pct,
                "cost_cny": s.cost_cny,
                "contribution_per_unit_weight": s.contribution_per_unit_weight,
            }
            for s in summary.sleeves
        ],
        "portfolio_total_return_pct": summary.portfolio_total_return_pct,
        "sum_of_sleeve_contributions_pct": summary.sum_of_sleeve_contributions_pct,
        "geometric_arithmetic_residual_pct": summary.geometric_arithmetic_residual_pct,
    }


__all__ = [
    "AttributionSummary",
    "SleeveAttribution",
    "attribution_payload",
    "compute_attribution",
    "render_attribution_table",
    "render_attribution_top_drawdown",
]
