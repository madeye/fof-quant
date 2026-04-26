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


_CONFIG_LABELS: dict[str, str] = {
    "project": "项目名称",
    "provider": "数据提供方",
    "start_date": "数据起始",
    "end_date": "数据截止",
    "benchmark": "基准指数",
    "cash_buffer": "现金缓冲",
    "max_weight": "单 Sleeve 最大权重",
    "min_holdings": "最小持仓数",
    "transaction_cost_bps": "佣金 (bps)",
    "slippage_bps": "滑点 (bps)",
    "llm_explanations": "启用 LLM 解读",
    "as_of": "数据日期",
    "total_aum_cny": "账户总资产 (元)",
    "backtest_start": "回测起始",
    "backtest_end": "回测结束",
    "rebalance_count": "调仓次数",
    "final_nav": "期末净值",
}

_CONSTRAINT_LABELS: dict[str, str] = {
    "min_holdings": "最小持仓数",
    "max_weight": "单 Sleeve 上限",
    "cash_buffer": "现金缓冲",
    "all_sleeves_filled": "所有 Sleeve 均有候选",
}

_ACTION_LABELS: dict[str, str] = {
    "open": "建仓",
    "close": "清仓",
    "buy": "加仓",
    "sell": "减仓",
    "hold": "持有",
    "initial": "初始建仓",
}


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
        "概览": _summary_rows(
            config_summary,
            sleeve_weights,
            extra=[("数据日期", analysis.as_of.isoformat()), ("账户总资产 (元)", total_aum_cny)],
        ),
        "Sleeve 选品": _sleeve_picks_rows(analysis),
        "目标配置": _target_plan_rows(target_plan),
        "调仓建议": _rebalance_rows(rebalance_lines),
    }
    if llm_narrative:
        sheets["LLM 解读"] = [
            ["LLM 解读 (仅作辅助说明，不参与任何计算)"],
            [llm_narrative],
        ]
    excel_path = output_dir / f"{stem}.xlsx"
    html_path = output_dir / f"{stem}.html"
    write_xlsx(excel_path, _format_sheets_for_excel(sheets))
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
        "概览": _summary_rows(
            config_summary,
            sleeve_weights,
            extra=_backtest_summary_extras(backtest),
        ),
        "Sleeve 选品": _sleeve_picks_rows(analysis),
        "绩效指标": _metrics_rows(backtest),
        "Sleeve 归因": _attribution_rows(attribution),
        "净值曲线": _nav_curve_rows(backtest),
        "调仓日志": _rebalance_log_rows(backtest),
        "回撤前 N 日": _top_drawdown_rows(backtest, top_n=20),
    }
    if llm_narrative:
        sheets["LLM 解读"] = [
            ["LLM 解读 (仅作辅助说明，不参与任何计算)"],
            [llm_narrative],
        ]
    excel_path = output_dir / f"{stem}.xlsx"
    html_path = output_dir / f"{stem}.html"
    write_xlsx(excel_path, _format_sheets_for_excel(sheets))
    html_path.write_text(_backtest_html(sheets, llm_narrative), encoding="utf-8")
    return ReportBundle(excel_path=excel_path, html_path=html_path)


# ----- sheet builders -----


def _summary_rows(
    config_summary: dict[str, object],
    sleeve_weights: dict[str, float],
    *,
    extra: list[tuple[str, object]] | None = None,
) -> SheetRows:
    rows: SheetRows = [["字段", "数值"]]
    for k, v in config_summary.items():
        rows.append([_CONFIG_LABELS.get(k, k), _to_cell(v)])
    rows.append(["—", "—"])
    rows.append(["Sleeve", "目标权重"])
    for sleeve, w in sleeve_weights.items():
        rows.append([sleeve, w])
    if extra:
        rows.append(["—", "—"])
        for k, v in extra:
            rows.append([_CONFIG_LABELS.get(k, k), _to_cell(v)])
    return rows


def _sleeve_picks_rows(analysis: BroadIndexAnalysis) -> SheetRows:
    rows: SheetRows = [
        [
            "Sleeve",
            "指数代码",
            "推荐 ETF",
            "ETF 名称",
            "管理人",
            "总费率%",
            "上市日期",
            "60日均成交额 (亿元)",
            "跟踪误差% (252日)",
            "信息比率 (252日)",
            "全收益基准?",
        ]
    ]
    for sp in analysis.sleeve_picks:
        if sp.pick is None:
            placeholder: list[str | int | float | bool | None] = [""] * 8
            rows.append([sp.spec.label, sp.spec.index_code, "(无符合条件 ETF)", *placeholder])
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
                m.avg_daily_amount_60d / 1e8,
                m.tracking_error_252d_pct if m.tracking_error_252d_pct is not None else "",
                m.info_ratio_252d if m.info_ratio_252d is not None else "",
                "是" if m.is_total_return_benchmark else "否",
            ]
        )
    return rows


def _target_plan_rows(target_plan: AllocationPlan) -> SheetRows:
    rows: SheetRows = [["ETF 代码", "目标权重", "评分", "选入理由"]]
    for h in target_plan.holdings:
        rows.append([h.etf_code, h.weight, h.score, h.reason])
    rows.append(["现金", target_plan.cash_weight, "", ""])
    rows.append(["—", "—", "—", "—"])
    rows.append(["约束", "是否满足"])
    for k, v in target_plan.constraint_checks.items():
        rows.append([_CONSTRAINT_LABELS.get(k, k), "是" if v else "否"])
    return rows


def _rebalance_rows(lines: list[RebalanceLine]) -> SheetRows:
    rows: SheetRows = [
        [
            "Sleeve",
            "ETF 代码",
            "目标权重",
            "当前权重",
            "偏离 (pp)",
            "动作",
            "目标金额 (元)",
            "调整金额 (元)",
            "最新价",
            "调仓股数 (100股整)",
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
                _ACTION_LABELS.get(line.action, line.action),
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
        ("回测起始", backtest.curve[0].trade_date.isoformat()),
        ("回测结束", backtest.curve[-1].trade_date.isoformat()),
        ("调仓次数", len(backtest.rebalances)),
        ("期末净值", backtest.curve[-1].nav),
    ]
    return extras


def _metrics_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [["指标", "策略", "基准"]]
    m = backtest.metrics
    b = backtest.benchmark_metrics
    cells = [
        ("总收益", m.total_return, b.total_return if b else None),
        ("年化收益 (CAGR)", m.annualized_return, b.annualized_return if b else None),
        ("年化波动率", m.volatility, b.volatility if b else None),
        ("Sharpe", m.sharpe, b.sharpe if b else None),
        ("最大回撤", m.max_drawdown, b.max_drawdown if b else None),
        ("Calmar", m.calmar, b.calmar if b else None),
        ("胜率", m.win_rate, b.win_rate if b else None),
        ("跟踪误差 vs 基准", m.tracking_error, b.tracking_error if b else None),
    ]
    for name, sv, bv in cells:
        rows.append([name, sv, bv if bv is not None else ""])
    return rows


def _attribution_rows(attribution: AttributionSummary) -> SheetRows:
    rows: SheetRows = [
        [
            "Sleeve",
            "贡献 %",
            "平均权重 %",
            "效率 (贡献/权重)",
            "持有天数",
            "调仓次数",
            "累计换手 %",
            "交易成本 (元)",
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
    rows.append(["算术贡献合计", attribution.sum_of_sleeve_contributions_pct, *pad])
    rows.append(["几何组合总收益", attribution.portfolio_total_return_pct, *pad])
    rows.append(["几何-算术差", attribution.geometric_arithmetic_residual_pct, *pad])
    return rows


def _nav_curve_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [["交易日", "净值", "日收益", "回撤"]]
    for p in backtest.curve:
        rows.append([p.trade_date.isoformat(), p.nav, p.daily_return, p.drawdown])
    return rows


def _rebalance_log_rows(backtest: BroadIndexBacktest) -> SheetRows:
    rows: SheetRows = [
        [
            "交易日",
            "调仓前净值",
            "换手率 %",
            "成本 (元)",
            "触发代码",
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
    rows: SheetRows = [["交易日", "日收益", "回撤"]]
    if not backtest.curve:
        return rows
    losers = sorted(backtest.curve, key=lambda p: p.daily_return)[:top_n]
    for p in losers:
        rows.append([p.trade_date.isoformat(), p.daily_return, p.drawdown])
    return rows


# ----- HTML rendering -----


def _signal_html(sheets: dict[str, SheetRows], narrative: str) -> str:
    return _wrap_html(
        title="宽基指数 FOF 调仓信号",
        sections=_sections_from_sheets(sheets),
        narrative=narrative,
    )


def _backtest_html(sheets: dict[str, SheetRows], narrative: str) -> str:
    return _wrap_html(
        title="宽基指数 FOF 回测报告",
        sections=_sections_from_sheets(sheets, big_sheets=("净值曲线",)),
        narrative=narrative,
    )


def _sections_from_sheets(
    sheets: dict[str, SheetRows],
    *,
    big_sheets: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, rows in sheets.items():
        if not rows or name == "LLM 解读":
            continue
        if name in big_sheets and len(rows) > 60:
            head = rows[:1] + rows[1:30]
            tail = rows[-30:]
            html = (
                _table_html(head)
                + "<p><em>…中间数据已省略，完整曲线见 Excel…</em></p>"
                + _table_html(tail)
            )
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
        f'<h2>LLM 解读</h2><p><em>仅作辅助说明，不参与任何评分、权重或回测计算。</em></p>'
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
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return _format_float(value)
    return str(value)


def _format_float(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        return str(value)
    if value == 0:
        return "0"
    # Pick precision based on magnitude — never scientific notation.
    abs_v = abs(value)
    if abs_v >= 1000:
        text = f"{value:,.2f}"
    elif abs_v >= 1:
        text = f"{value:,.4f}"
    else:
        text = f"{value:.6f}"
    # Trim trailing zeros (but keep at least 2 decimals when present)
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text


def _to_cell(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _format_sheets_for_excel(sheets: dict[str, SheetRows]) -> dict[str, SheetRows]:
    """Pre-format floats to formatted strings before they reach the xlsx writer.
    Excel's General number format falls to scientific notation for values below
    1e-4 (and above ~1e11), which we never want in a research report. By
    rendering floats as already-formatted strings we sidestep that entirely;
    cells become text but the formatting matches the HTML view exactly."""
    formatted: dict[str, SheetRows] = {}
    for name, rows in sheets.items():
        formatted[name] = [
            [_excel_cell(value) for value in row]
            for row in rows
        ]
    return formatted


def _excel_cell(value: str | int | float | bool | None) -> str | int | float | bool | None:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return _format_float(value)
    return value
