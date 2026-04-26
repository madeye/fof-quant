from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fof_quant.allocation.engine import AllocationPlan

Action = Literal["initial", "buy", "sell", "hold", "open", "close"]


@dataclass(frozen=True)
class RebalanceLine:
    ts_code: str
    sleeve: str
    target_weight: float
    current_weight: float
    drift_pp: float  # absolute pp = (current - target) * 100
    drift_rel_pct: float  # relative % = drift_pp / target_pp * 100; nan if target == 0
    action: Action
    target_notional_cny: float
    delta_notional_cny: float
    last_price: float
    delta_shares_lot100: int  # signed; rounded toward zero in 100-share lots


def compute_rebalance(
    target_plan: AllocationPlan,
    sleeve_by_code: dict[str, str],
    current_weights: dict[str, float],
    last_price: dict[str, float],
    total_aum_cny: float,
    *,
    abs_band_pp: float = 5.0,
    rel_band_pct: float = 25.0,
    force: bool = False,
) -> list[RebalanceLine]:
    """Combine target weights with current weights and produce per-position
    rebalance instructions. A line triggers a trade when its absolute drift
    exceeds abs_band_pp OR its relative drift exceeds rel_band_pct, OR when
    the position is being opened/closed, OR when force=True (semi-annual).
    """
    lines: list[RebalanceLine] = []
    target_by_code = {row.etf_code: row.weight for row in target_plan.holdings}
    all_codes = sorted(set(target_by_code) | set(current_weights))

    for code in all_codes:
        target_w = target_by_code.get(code, 0.0)
        current_w = current_weights.get(code, 0.0)
        drift_pp = (current_w - target_w) * 100.0
        drift_rel_pct = (
            drift_pp / (target_w * 100.0) * 100.0 if target_w > 0 else float("nan")
        )
        triggered = (
            force
            or (target_w > 0 and current_w == 0.0)
            or (target_w == 0.0 and current_w > 0)
            or abs(drift_pp) > abs_band_pp
            or (target_w > 0 and abs(drift_rel_pct) > rel_band_pct)
        )
        action = _action_for(target_w, current_w, triggered)
        target_notional = target_w * total_aum_cny if triggered else current_w * total_aum_cny
        delta_notional = target_notional - current_w * total_aum_cny
        price = last_price.get(code, 0.0)
        delta_shares = (
            int(delta_notional / price // 100) * 100 if price > 0 and triggered else 0
        )
        lines.append(
            RebalanceLine(
                ts_code=code,
                sleeve=sleeve_by_code.get(code, ""),
                target_weight=target_w,
                current_weight=current_w,
                drift_pp=drift_pp,
                drift_rel_pct=drift_rel_pct,
                action=action,
                target_notional_cny=target_notional,
                delta_notional_cny=delta_notional,
                last_price=price,
                delta_shares_lot100=delta_shares,
            )
        )
    return lines


def _action_for(target: float, current: float, triggered: bool) -> Action:
    if target > 0 and current == 0.0:
        return "open"
    if target == 0.0 and current > 0:
        return "close"
    if not triggered:
        return "hold"
    if target > current:
        return "buy"
    if target < current:
        return "sell"
    return "hold"
