from __future__ import annotations

from fof_quant.allocation.engine import AllocationPlan, AllocationRow
from fof_quant.analysis.broad_index import BroadIndexAnalysis

# Default 5-sleeve FOF mix. Tilts toward 中证红利低波 (35%) because it dominated
# the analysis/sweep grid on the cached 2021–2026 broad-index window:
# Sharpe 0.640, CAGR 8.66%, MaxDD -16.4%, Calmar 0.53 — the best of 42 sweep
# combos and ~10x the benchmark Sharpe (沪深300TR Sharpe 0.065). 沪深300 and
# 中证500 are intentionally dropped because they overlap with 中证A500
# (corr 0.98) and 中证1000 (corr 0.97) respectively.
DEFAULT_SLEEVE_WEIGHTS: dict[str, float] = {
    "中证A500": 0.30,
    "中证1000": 0.15,
    "创业板指": 0.10,
    "科创50": 0.10,
    "中证红利低波": 0.35,
}


def build_target_plan(
    analysis: BroadIndexAnalysis,
    *,
    sleeve_weights: dict[str, float] = DEFAULT_SLEEVE_WEIGHTS,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
) -> AllocationPlan:
    """Convert per-sleeve picks + sleeve weight map into an AllocationPlan.
    Skipped sleeves (no eligible pick) have their weight redistributed to the
    cash bucket so the plan stays internally consistent.
    """
    holdings: list[AllocationRow] = []
    skipped_weight = 0.0
    for spec in (sp.spec for sp in analysis.sleeve_picks):
        weight = sleeve_weights.get(spec.label, 0.0)
        if weight <= 0:
            continue
        pick_for_sleeve = next(
            (sp.pick for sp in analysis.sleeve_picks if sp.spec.label == spec.label),
            None,
        )
        if pick_for_sleeve is None:
            skipped_weight += weight
            continue
        capped = min(weight, max_weight)
        holdings.append(
            AllocationRow(
                etf_code=pick_for_sleeve.ts_code,
                weight=capped,
                score=pick_for_sleeve.info_ratio_252d or 0.0,
                reason=f"{spec.label} sleeve pick ({pick_for_sleeve.name})",
            )
        )
        if capped < weight:
            skipped_weight += weight - capped

    allocated = sum(row.weight for row in holdings)
    cash_weight = max(cash_buffer, 1.0 - allocated)
    return AllocationPlan(
        holdings=holdings,
        cash_weight=cash_weight,
        constraint_checks={
            "min_holdings": len(holdings) >= 1,
            "max_weight": all(row.weight <= max_weight for row in holdings),
            "cash_buffer": cash_weight >= cash_buffer,
            "all_sleeves_filled": skipped_weight == 0,
        },
    )


def sleeve_by_code(analysis: BroadIndexAnalysis) -> dict[str, str]:
    out: dict[str, str] = {}
    for sp in analysis.sleeve_picks:
        if sp.pick is not None:
            out[sp.pick.ts_code] = sp.spec.label
        for runner in sp.runners_up:
            out.setdefault(runner.ts_code, sp.spec.label)
    return out
