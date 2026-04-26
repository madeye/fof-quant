from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from fof_quant.allocation.engine import AllocationPlan
from fof_quant.analysis.broad_index import (
    BroadIndexAnalysis,
)
from fof_quant.analysis.broad_index import (
    analyze as analyze_broad_index,
)
from fof_quant.analysis.broad_index_allocation import (
    DEFAULT_SLEEVE_WEIGHTS,
    build_target_plan,
    sleeve_by_code,
)
from fof_quant.data.broad_index import BroadIndexFetchResult, load_broad_index
from fof_quant.portfolio.holdings import CurrentPortfolio, load_holdings
from fof_quant.portfolio.rebalance import RebalanceLine, compute_rebalance


@dataclass(frozen=True)
class BroadIndexRunArtifacts:
    target_plan: AllocationPlan
    rebalance_lines: list[RebalanceLine]
    total_aum_cny: float
    manifest_path: Path


def run_broad_index_pipeline(
    *,
    cache_dir: Path,
    output_dir: Path,
    holdings_path: Path | None,
    initial_cash_if_empty: float,
    sleeve_weights: dict[str, float] | None = None,
    cash_buffer: float = 0.01,
    max_weight: float = 0.4,
    abs_band_pp: float = 5.0,
    rel_band_pct: float = 25.0,
    force_rebalance: bool = False,
) -> BroadIndexRunArtifacts:
    weights = sleeve_weights or DEFAULT_SLEEVE_WEIGHTS
    fetched = load_broad_index(cache_dir)
    analysis = analyze_broad_index(fetched)
    target_plan = build_target_plan(
        analysis,
        sleeve_weights=weights,
        cash_buffer=cash_buffer,
        max_weight=max_weight,
    )
    last_price = _last_close_per_code(fetched)
    portfolio = (
        load_holdings(holdings_path)
        if holdings_path is not None
        else CurrentPortfolio.empty(as_of=analysis.as_of, cash_cny=initial_cash_if_empty)
    )
    aum = portfolio.total_aum(last_price)
    current_weights = portfolio.weights(last_price)
    lines = compute_rebalance(
        target_plan,
        sleeve_by_code=sleeve_by_code(analysis),
        current_weights=current_weights,
        last_price=last_price,
        total_aum_cny=aum,
        abs_band_pp=abs_band_pp,
        rel_band_pct=rel_band_pct,
        force=force_rebalance,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"broad_index_rebalance_{analysis.as_of:%Y%m%d}.json"
    manifest_path.write_text(
        json.dumps(
            _manifest_payload(analysis, target_plan, lines, aum, weights),
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    return BroadIndexRunArtifacts(
        target_plan=target_plan,
        rebalance_lines=lines,
        total_aum_cny=aum,
        manifest_path=manifest_path,
    )


def render_rebalance_table(lines: list[RebalanceLine], total_aum_cny: float) -> str:
    header = (
        f"Rebalance signal — total AUM ¥{total_aum_cny:,.0f}\n"
        f"{'sleeve':12s}  {'code':10s}  {'tgt%':>6s}  {'cur%':>6s}  "
        f"{'drift_pp':>8s}  {'action':>6s}  {'Δnotional¥':>12s}  {'Δshares':>10s}"
    )
    rule = "-" * len(header.splitlines()[1])
    body = []
    for line in lines:
        body.append(
            f"{line.sleeve:12s}  {line.ts_code:10s}  "
            f"{line.target_weight * 100:6.2f}  {line.current_weight * 100:6.2f}  "
            f"{line.drift_pp:+8.2f}  {line.action:>6s}  "
            f"{line.delta_notional_cny:12,.0f}  {line.delta_shares_lot100:+10d}"
        )
    return "\n".join([header, rule, *body])


def _last_close_per_code(fetched: BroadIndexFetchResult) -> dict[str, float]:
    latest: dict[str, tuple[str, float]] = {}
    for row in fetched.etf_daily.rows:
        code = str(row["ts_code"])
        trade_date = str(row["trade_date"])
        close = row.get("close")
        if close is None:
            continue
        prior = latest.get(code)
        if prior is None or trade_date > prior[0]:
            latest[code] = (trade_date, float(close))
    return {code: price for code, (_, price) in latest.items()}


def _manifest_payload(
    analysis: BroadIndexAnalysis,
    target_plan: AllocationPlan,
    lines: list[RebalanceLine],
    total_aum_cny: float,
    sleeve_weights: dict[str, float],
) -> dict[str, object]:
    return {
        "as_of": analysis.as_of.isoformat(),
        "total_aum_cny": total_aum_cny,
        "sleeve_weights": sleeve_weights,
        "target_plan": {
            "holdings": [asdict(row) for row in target_plan.holdings],
            "cash_weight": target_plan.cash_weight,
            "constraint_checks": target_plan.constraint_checks,
        },
        "rebalance_lines": [asdict(line) for line in lines],
        "trade_count": sum(1 for line in lines if line.action not in ("hold",)),
    }


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"object of type {type(value)} is not JSON serializable")
