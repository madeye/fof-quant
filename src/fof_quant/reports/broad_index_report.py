from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from fof_quant.allocation.engine import AllocationPlan
from fof_quant.analysis.attribution import (
    AttributionSummary,
    compute_attribution,
)
from fof_quant.analysis.broad_index import BroadIndexAnalysis
from fof_quant.backtest_broad_index import BroadIndexBacktest
from fof_quant.portfolio.rebalance import RebalanceLine
from fof_quant.reports.xlsx import SheetRows, write_xlsx


@dataclass(frozen=True)
class ReportBundle:
    excel_path: Path
    html_path: Path


def write_signal_report(
    *,
    output_dir: Path,
    config_summary: dict[str, object],
    analysis: BroadIndexAnalysis,
    target_plan: AllocationPlan,
    rebalance_lines: list[RebalanceLine],
    total_aum_cny: float,
    sleeve_weights: dict[str, float],
    llm_narrative: str = "",
) -> ReportBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"broad_index_signal_{analysis.as_of:%Y%m%d}"
    sheets: dict[str, SheetRows] = {
        "Summary": _summary_rows(
            config_summary,
            sleeve_weights,
            extra=[("as_of", analysis.as_of.isoformat()), ("total_aum_cny", total_aum_cny)],
        ),
        "Sleeve picks": _sleeve_picks_rows(analysis),
        "Target plan": _target_plan_rows(target_plan),
        "Rebalance": _rebalance_rows(rebalance_lines),
    }
    if llm_narrative:
        sheets["Narrative"] = [
            ["LLM narrative (assistance only — not a calculation input)"],
            [llm_narrative],
        ]
    excel_path = output_dir / f"{stem}.xlsx"
    html_path = output_dir / f"{stem}.html"
    write_xlsx(excel_path, sheets)
    html_path.write_text(_signal_html(sheets, llm_narrative), encoding="utf-8")
    return ReportBundle(excel_path=excel_path, html_path=html_path)


def write_backtest_report(
    *,
    output_dir: Path,
    config_summary: dict[str, object],
    analysis: BroadIndexAnalysis,
    backtest: BroadIndexBacktest,
    sleeve_weights: dict[str, float],
    llm_narrative: str = "",
) -> ReportBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    end = backtest.curve[-1].trade_date if backtest.curve else analysis.as_of
    stem = f"broad_index_backtest_{end:%Y%m%d}"
    attribution = compute_attribution(backtest)
    sheets: dict[str, SheetRows] = {
        "Summary": _summary_rows(
            config_summary,
            sleeve_weights,
            extra=_backtest_summary_extras(backtest),
        ),
        "Sleeve picks": _sleeve_picks_rows(analysis),
        "Metrics": _metrics_rows(backtest),
        "Attribution": _attribution_rows(attribution),
        "NAV curve": _nav_curve_rows(backtest),
        "Rebalance log": _rebalance_log_rows(backtest),
        "Top drawdown days": _top_drawdown_rows(backtest, top_n=20),
    }
    if llm_narrative:
        sheets["Narrative"] = [
            ["LLM narrative (assistance only — not a calculation input)"],
            [llm_narrative],
        ]
    excel_path = output_dir / f"{stem}.xlsx"
    html_path = output_dir / f"{stem}.html"
    write_xlsx(excel_path, sheets)
    html_path.write_text(_backtest_html(sheets, llm_narrative), encoding="utf-8")
    return ReportBundle(excel_path=excel_path, html_path=html_path)


# ----- sheet builders -----


def _summary_rows(
    config_summary: dict[str, object],
    sleeve_weights: dict[str, float],
    *,
    extra: list[tuple[str, object]] | None = None,
) -> SheetRows:
    rows: SheetRows = [["Field", "Value"]]
    for k, v in config_summary.items():
        rows.append([k, _to_cell(v)])
    rows.append(["—", "—"])
    rows.append(["sleeve", "target_weight"])
    for sleeve, w in sleeve_weights.items():
        rows.append([sleeve, w])
    if extra:
        rows.append(["—", "—"])
        for k, v in extra:
            rows.append([k, _to_cell(v)])
    return rows


def _sleeve_picks_rows(analysis: BroadIndexAnalysis) -> SheetRows:
    rows: SheetRows = [
        [
            "sleeve",
            "index_code",
            "pick_code",
            "pick_name",
            "management",
            "fee_pct",
            "list_date",
            "60d_avg_amount_cny",
            "te_252d_pct",
            "ir_252d",
            "tr_benchmark",
        ]
    ]
    for sp in analysis.sleeve_picks:
        if sp.pick is None:
            placeholder: list[str | int | float | bool | None] = [""] * 8
            rows.append([sp.spec.label, sp.spec.index_code, "(no eligible pick)", *placeholder])
            continue
        m = sp.pick
        rows.append(
            [
                sp.spec.label,
                sp.spec.index_code,
                m.ts_code,
                m.name,
                m.management,
                m.fee_total_pct,
                m.list_date.isoformat(),
                m.avg_daily_amount_60d,
                m.tracking_error_252d_pct if m.tracking_error_252d_pct is not None else "",
                m.info_ratio_252d if m.info_ratio_252d is not None else "",
                "Y" if m.is_total_return_benchmark else "N",
            ]
        )
    return rows


def _target_plan_rows(target_plan: AllocationPlan) -> SheetRows:
    rows: SheetRows = [["etf_code", "weight", "score", "reason"]]
    for h in target_plan.holdings:
        rows.append([h.etf_code, h.weight, h.score, h.reason])
    rows.append(["cash", target_plan.cash_weight, "", ""])
    rows.append(["—", "—", "—", "—"])
    rows.append(["constraint", "passed"])
    for k, v in target_plan.constraint_checks.items():
        rows.append([k, v])
    return rows


def _rebalance_rows(lines: list[RebalanceLine]) -> SheetRows:
    rows: SheetRows = [
        [
            "sleeve",
            "ts_code",
            "target_weight",
            "current_weight",
            "drift_pp",
            "action",
            "target_notional_cny",
            "delta_notional_cny",
            "last_price",
            "delta_shares_lot100",
        ]
    ]
    for line in lines:
        rows.append(
            [
                line.sleeve,
                line.ts_code,
                line.target_weight,
                line.current_weight,
                line.drift_pp,
                line.action,
                line.target_notional_cny,
                line.delta_notional_cny,
                line.last_price,
                line.delta_shares_lot100,
            ]
        )
    return rows


def _backtest_summary_extras(backtest: BroadIndexBacktest) -> list[tuple[str, object]]:
    if not backtest.curve:
        return []
    extras: list[tuple[str, object]] = [
        ("backtest_start", backtest.curve[0].trade_date.isoformat()),
        ("backtest_end", backtest.curve[-1].trade_date.isoformat()),
        ("rebalance_count", len(backtest.rebalances)),
        ("final_nav", backtest.curve[-1].nav),
    ]
    return extras


def _metrics_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [["metric", "strategy", "benchmark"]]
    m = backtest.metrics
    b = backtest.benchmark_metrics
    cells = [
        ("total_return", m.total_return, b.total_return if b else None),
        ("annualized_return", m.annualized_return, b.annualized_return if b else None),
        ("volatility", m.volatility, b.volatility if b else None),
        ("sharpe", m.sharpe, b.sharpe if b else None),
        ("max_drawdown", m.max_drawdown, b.max_drawdown if b else None),
        ("calmar", m.calmar, b.calmar if b else None),
        ("win_rate", m.win_rate, b.win_rate if b else None),
        ("tracking_error", m.tracking_error, b.tracking_error if b else None),
    ]
    for name, sv, bv in cells:
        rows.append([name, sv, bv if bv is not None else ""])
    return rows


def _attribution_rows(attribution: AttributionSummary) -> SheetRows:
    rows: SheetRows = [
        [
            "sleeve",
            "contribution_pct",
            "avg_weight_pct",
            "efficiency",
            "days_held",
            "rebalance_count",
            "turnover_pct",
            "cost_cny",
        ]
    ]
    for s in attribution.sleeves:
        rows.append(
            [
                s.sleeve,
                s.contribution_pct,
                s.avg_weight_pct,
                s.contribution_per_unit_weight,
                s.days_held,
                s.rebalance_count,
                s.turnover_pct,
                s.cost_cny,
            ]
        )
    pad: list[str | int | float | bool | None] = ["", "", "", "", "", "", ""]
    rows.append(["—"] * 8)
    rows.append(["sum_arithmetic", attribution.sum_of_sleeve_contributions_pct, *pad])
    rows.append(["portfolio_geometric", attribution.portfolio_total_return_pct, *pad])
    rows.append(["residual", attribution.geometric_arithmetic_residual_pct, *pad])
    return rows


def _nav_curve_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [["trade_date", "nav", "daily_return", "drawdown"]]
    for p in backtest.curve:
        rows.append([p.trade_date.isoformat(), p.nav, p.daily_return, p.drawdown])
    return rows


def _rebalance_log_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [
        [
            "trade_date",
            "nav_before",
            "turnover_pct",
            "cost_cny",
            "triggered_codes",
        ]
    ]
    for r in backtest.rebalances:
        rows.append(
            [
                r.trade_date.isoformat(),
                r.nav_before,
                r.turnover_pct,
                r.cost_cny,
                ",".join(r.triggered_codes),
            ]
        )
    return rows


def _top_drawdown_rows(backtest: BroadIndexBacktest, *, top_n: int) -> SheetRows:
    rows: SheetRows = [["trade_date", "daily_return", "drawdown"]]
    if not backtest.curve:
        return rows
    losers = sorted(backtest.curve, key=lambda p: p.daily_return)[:top_n]
    for p in losers:
        rows.append([p.trade_date.isoformat(), p.daily_return, p.drawdown])
    return rows


# ----- HTML rendering -----


def _signal_html(sheets: dict[str, SheetRows], narrative: str) -> str:
    return _wrap_html(
        title="Broad-index FOF rebalance signal",
        sections=_sections_from_sheets(sheets),
        narrative=narrative,
    )


def _backtest_html(sheets: dict[str, SheetRows], narrative: str) -> str:
    return _wrap_html(
        title="Broad-index FOF backtest report",
        sections=_sections_from_sheets(sheets, big_sheets=("NAV curve",)),
        narrative=narrative,
    )


def _sections_from_sheets(
    sheets: dict[str, SheetRows],
    *,
    big_sheets: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, rows in sheets.items():
        if not rows or name == "Narrative":
            continue
        if name in big_sheets and len(rows) > 60:
            head = rows[:1] + rows[1:30]
            tail = rows[-30:]
            html = _table_html(head) + "<p><em>…rows truncated…</em></p>" + _table_html(tail)
        else:
            html = _table_html(rows)
        out.append((name, html))
    return out


def _table_html(rows: SheetRows) -> str:
    if not rows:
        return ""
    header = "".join(f"<th>{escape(_cell_str(c))}</th>" for c in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_cell_str(c))}</td>" for c in row) + "</tr>"
        for row in rows[1:]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def _wrap_html(*, title: str, sections: list[tuple[str, str]], narrative: str) -> str:
    blocks = "\n".join(f"<h2>{escape(name)}</h2>{html}" for name, html in sections)
    narrative_block = (
        f'<h2>LLM narrative</h2><p><em>Assistance only — never feeds calculations.</em></p>'
        f"<pre>{escape(narrative)}</pre>"
        if narrative
        else ""
    )
    css = (
        "body{font-family:system-ui,-apple-system,sans-serif;"
        "max-width:1100px;margin:1.5em auto;color:#1c1c1e}"
        "h1{border-bottom:2px solid #1c1c1e;padding-bottom:.25em}"
        "h2{margin-top:1.5em;border-bottom:1px solid #ccc;padding-bottom:.25em}"
        "table{border-collapse:collapse;width:100%;margin:.5em 0;font-size:.92em}"
        "th,td{padding:4px 8px;border:1px solid #d0d0d0;text-align:right}"
        "th{background:#f4f4f6;text-align:left}"
        "td:first-child,th:first-child{text-align:left}"
        "pre{background:#f6f8fa;padding:1em;overflow-x:auto;white-space:pre-wrap}"
    )
    return (
        f"<!doctype html>\n<html lang=\"zh-Hans\">\n"
        f"<head><meta charset=\"utf-8\"><title>{escape(title)}</title>"
        f"<style>{css}</style></head>\n<body>\n"
        f"<h1>{escape(title)}</h1>\n{blocks}\n{narrative_block}\n"
        "</body>\n</html>\n"
    )


def _cell_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _to_cell(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
