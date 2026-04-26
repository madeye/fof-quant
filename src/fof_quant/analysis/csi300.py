from __future__ import annotations

import csv
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fof_quant.data.csi300 import CSI300_BENCHMARK, CSI300FetchResult


@dataclass(frozen=True)
class ETFMetrics:
    ts_code: str
    name: str
    management: str
    list_date: date
    listing_days: int
    fee_total_pct: float
    obs_days: int
    avg_daily_amount_60d: float
    return_252d_pct: float | None
    vol_252d_pct: float | None
    sharpe_252d: float | None
    tracking_error_252d_pct: float | None
    info_ratio_252d: float | None


@dataclass(frozen=True)
class CSI300Analysis:
    as_of: date
    benchmark_ts_code: str
    metrics: list[ETFMetrics] = field(default_factory=list)


def analyze(result: CSI300FetchResult, *, as_of: date | None = None) -> CSI300Analysis:
    benchmark_returns = _daily_returns_from(result.index_total_return.rows, "trade_date", "close")
    universe_index = {row["ts_code"]: row for row in result.universe.rows}

    nav_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in result.fund_nav.rows:
        if row.get("adj_nav") is None:
            continue
        nav_by_code.setdefault(row["ts_code"], []).append(row)

    amount_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in result.etf_daily.rows:
        amount_by_code.setdefault(row["ts_code"], []).append(row)

    resolved_as_of = as_of or _max_date(result.index_total_return.rows)
    metrics = [
        _metrics_for_etf(
            code,
            nav_by_code.get(code, []),
            amount_by_code.get(code, []),
            universe_index[code],
            benchmark_returns,
            resolved_as_of,
        )
        for code in sorted(universe_index)
    ]
    metrics.sort(key=lambda m: (m.return_252d_pct is None, -(m.return_252d_pct or 0.0)))
    return CSI300Analysis(as_of=resolved_as_of, benchmark_ts_code=CSI300_BENCHMARK, metrics=metrics)


def write_csv(analysis: CSI300Analysis, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"csi300_etfs_{analysis.as_of:%Y%m%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "ts_code",
                "name",
                "management",
                "list_date",
                "listing_days",
                "fee_total_pct",
                "obs_days",
                "avg_daily_amount_60d_cny",
                "return_252d_pct",
                "vol_252d_pct",
                "sharpe_252d",
                "tracking_error_252d_pct",
                "info_ratio_252d",
            ]
        )
        for m in analysis.metrics:
            writer.writerow(
                [
                    m.ts_code,
                    m.name,
                    m.management,
                    m.list_date.isoformat(),
                    m.listing_days,
                    f"{m.fee_total_pct:.3f}",
                    m.obs_days,
                    f"{m.avg_daily_amount_60d:.0f}",
                    _fmt(m.return_252d_pct),
                    _fmt(m.vol_252d_pct),
                    _fmt(m.sharpe_252d),
                    _fmt(m.tracking_error_252d_pct),
                    _fmt(m.info_ratio_252d),
                ]
            )
    return path


def render_table(analysis: CSI300Analysis, *, top: int = 25) -> str:
    header = (
        f"CSI 300 ETF analysis — {len(analysis.metrics)} funds, as of {analysis.as_of:%Y-%m-%d} "
        f"(benchmark {analysis.benchmark_ts_code})"
    )
    columns = [
        ("code", 10),
        ("name", 22),
        ("mgr", 14),
        ("listed", 10),
        ("fee%", 6),
        ("amt60d¥M", 11),
        ("ret252%", 9),
        ("vol252%", 9),
        ("sharpe", 7),
        ("te%", 7),
        ("ir", 7),
    ]
    title_row = "  ".join(name.rjust(width) for name, width in columns)
    rule = "-" * len(title_row)
    body_lines: list[str] = []
    for m in analysis.metrics[:top]:
        body_lines.append(
            "  ".join(
                [
                    m.ts_code.rjust(10),
                    _trim(m.name, 22).rjust(22),
                    _trim(m.management, 14).rjust(14),
                    m.list_date.isoformat().rjust(10),
                    f"{m.fee_total_pct:.2f}".rjust(6),
                    f"{m.avg_daily_amount_60d / 1e6:.1f}".rjust(11),
                    _fmt(m.return_252d_pct, width=9),
                    _fmt(m.vol_252d_pct, width=9),
                    _fmt(m.sharpe_252d, width=7),
                    _fmt(m.tracking_error_252d_pct, width=7),
                    _fmt(m.info_ratio_252d, width=7),
                ]
            )
        )
    return "\n".join([header, rule, title_row, rule, *body_lines])


def _metrics_for_etf(
    code: str,
    nav_rows: list[dict[str, Any]],
    amount_rows: list[dict[str, Any]],
    universe_row: dict[str, Any],
    benchmark_returns: dict[date, float],
    as_of: date,
) -> ETFMetrics:
    nav_sorted = sorted(nav_rows, key=lambda r: str(r["nav_date"]))
    series = [(_parse_date(str(r["nav_date"])), float(r["adj_nav"])) for r in nav_sorted]
    amounts_sorted = sorted(amount_rows, key=lambda r: str(r["trade_date"]))
    amounts = [float(r.get("amount") or 0.0) for r in amounts_sorted]
    list_date = _parse_date(str(universe_row["list_date"]))
    listing_days = (as_of - list_date).days
    m_fee = float(universe_row.get("m_fee") or 0.0)
    c_fee = float(universe_row.get("c_fee") or 0.0)
    fee_total = m_fee + c_fee

    avg_amount_60d = _mean(amounts[-60:]) * 1000.0  # tushare amount is in ¥thousand
    dated_returns = _dated_returns(series)
    paired = [(d, r, benchmark_returns[d]) for d, r in dated_returns if d in benchmark_returns]
    paired_252 = paired[-252:]
    etf_r = [r for _, r, _ in paired_252]
    bench_r = [b for _, _, b in paired_252]

    return ETFMetrics(
        ts_code=code,
        name=str(universe_row["name"]),
        management=str(universe_row.get("management") or ""),
        list_date=list_date,
        listing_days=listing_days,
        fee_total_pct=fee_total,
        obs_days=len(series),
        avg_daily_amount_60d=avg_amount_60d,
        return_252d_pct=_period_return_pct(etf_r),
        vol_252d_pct=_annualized_vol_pct(etf_r),
        sharpe_252d=_sharpe(etf_r),
        tracking_error_252d_pct=_tracking_error_pct(etf_r, bench_r),
        info_ratio_252d=_information_ratio(etf_r, bench_r),
    )


def _dated_returns(series: list[tuple[date, float]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    for i in range(1, len(series)):
        d, close = series[i]
        prev_close = series[i - 1][1]
        if prev_close > 0:
            out.append((d, close / prev_close - 1.0))
    return out


def _daily_returns_from(
    rows: Sequence[dict[str, Any]],
    date_field: str,
    value_field: str,
) -> dict[date, float]:
    sorted_rows = sorted(rows, key=lambda r: str(r[date_field]))
    out: dict[date, float] = {}
    prev: float | None = None
    for r in sorted_rows:
        value = float(r[value_field])
        if prev is not None and prev > 0:
            out[_parse_date(str(r[date_field]))] = value / prev - 1.0
        prev = value
    return out


def _period_return_pct(returns: list[float]) -> float | None:
    if not returns:
        return None
    cum = 1.0
    for r in returns:
        cum *= 1.0 + r
    return (cum - 1.0) * 100.0


def _annualized_vol_pct(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var) * math.sqrt(252.0) * 100.0


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    if var <= 0:
        return None
    return (mean / math.sqrt(var)) * math.sqrt(252.0)


def _tracking_error_pct(etf: list[float], bench: list[float]) -> float | None:
    if len(etf) < 2 or len(etf) != len(bench):
        return None
    diffs = [a - b for a, b in zip(etf, bench, strict=True)]
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1)
    return math.sqrt(var) * math.sqrt(252.0) * 100.0


def _information_ratio(etf: list[float], bench: list[float]) -> float | None:
    if len(etf) < 2 or len(etf) != len(bench):
        return None
    diffs = [a - b for a, b in zip(etf, bench, strict=True)]
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1)
    if var <= 0:
        return None
    return (mean / math.sqrt(var)) * math.sqrt(252.0)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _max_date(rows: Sequence[dict[str, Any]]) -> date:
    return max(_parse_date(str(r["trade_date"])) for r in rows)


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def _trim(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _fmt(value: float | None, *, width: int = 0) -> str:
    text = "—" if value is None else f"{value:.2f}"
    return text.rjust(width) if width else text
