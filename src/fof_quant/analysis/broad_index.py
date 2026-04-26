from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fof_quant.data.broad_index import BROAD_INDEX_SPECS, BroadIndexFetchResult, IndexSpec


@dataclass(frozen=True)
class ETFMetrics:
    sleeve: str
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
    is_total_return_benchmark: bool


@dataclass(frozen=True)
class SleevePick:
    spec: IndexSpec
    pick: ETFMetrics | None
    runners_up: list[ETFMetrics] = field(default_factory=list)
    sleeve_return_252d_pct: float | None = None
    sleeve_vol_252d_pct: float | None = None


@dataclass(frozen=True)
class BroadIndexAnalysis:
    as_of: date
    sleeve_picks: list[SleevePick] = field(default_factory=list)
    correlation: dict[tuple[str, str], float] = field(default_factory=dict)


def analyze(result: BroadIndexFetchResult, *, as_of: date | None = None) -> BroadIndexAnalysis:
    benchmark_returns_by_code = _benchmark_returns_by_code(result.benchmarks.rows)
    universe_index = {row["ts_code"]: row for row in result.universe.rows}

    nav_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in result.fund_nav.rows:
        if row.get("adj_nav") is None:
            continue
        nav_by_code.setdefault(str(row["ts_code"]), []).append(row)
    amount_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in result.etf_daily.rows:
        amount_by_code.setdefault(str(row["ts_code"]), []).append(row)

    resolved_as_of = as_of or _max_benchmark_date(result.benchmarks.rows)

    sleeve_picks: list[SleevePick] = []
    for spec in result.specs:
        bench_returns = benchmark_returns_by_code.get(spec.total_return_code, {})
        sleeve_codes = [
            code
            for code, urow in universe_index.items()
            if urow.get("_sleeve") == spec.label
        ]
        sleeve_metrics = [
            _metrics_for_etf(
                spec,
                code,
                nav_by_code.get(code, []),
                amount_by_code.get(code, []),
                universe_index[code],
                bench_returns,
                resolved_as_of,
            )
            for code in sleeve_codes
        ]
        ranked = _rank_sleeve(sleeve_metrics)
        bench_ret_252 = _period_return_pct(list(bench_returns.values())[-252:])
        bench_vol_252 = _annualized_vol_pct(list(bench_returns.values())[-252:])
        sleeve_picks.append(
            SleevePick(
                spec=spec,
                pick=ranked[0] if ranked else None,
                runners_up=ranked[1:4],
                sleeve_return_252d_pct=bench_ret_252,
                sleeve_vol_252d_pct=bench_vol_252,
            )
        )

    correlation = _benchmark_correlation(benchmark_returns_by_code, result.specs)
    return BroadIndexAnalysis(
        as_of=resolved_as_of, sleeve_picks=sleeve_picks, correlation=correlation
    )


def render_picks(analysis: BroadIndexAnalysis) -> str:
    lines: list[str] = [
        f"Broad-index ETF picks — as of {analysis.as_of:%Y-%m-%d}",
        "=" * 110,
        f"{'sleeve':12s}  {'index':9s}  {'ret252%':8s}  {'vol%':6s}  "
        f"  {'pick':10s}  {'name':22s}  {'fee%':5s}  "
        f"{'amt¥M':8s}  {'te%':6s}  {'ir':6s}  {'TR?':3s}",
        "-" * 110,
    ]
    for sp in analysis.sleeve_picks:
        if sp.pick is None:
            lines.append(f"{sp.spec.label:12s}  {sp.spec.index_code:9s}  (no ETF)")
            continue
        m = sp.pick
        lines.append(
            f"{sp.spec.label:12s}  "
            f"{sp.spec.index_code:9s}  "
            f"{_fmt(sp.sleeve_return_252d_pct, 8)}  "
            f"{_fmt(sp.sleeve_vol_252d_pct, 6)}  "
            f"  {m.ts_code:10s}  "
            f"{_trim(m.name, 22).ljust(22)}  "
            f"{m.fee_total_pct:5.2f}  "
            f"{m.avg_daily_amount_60d / 1e6:8.1f}  "
            f"{_fmt(m.tracking_error_252d_pct, 6)}  "
            f"{_fmt(m.info_ratio_252d, 6)}  "
            f"{'Y' if m.is_total_return_benchmark else 'N':3s}"
        )
    lines.append("")
    lines.append("Runners-up per sleeve:")
    for sp in analysis.sleeve_picks:
        if not sp.runners_up:
            continue
        rivals = ", ".join(
            f"{m.ts_code}({m.name[:10]} fee{m.fee_total_pct:.2f}"
            f" amt¥M{m.avg_daily_amount_60d / 1e6:.1f} ir{_fmt(m.info_ratio_252d)})"
            for m in sp.runners_up
        )
        lines.append(f"  {sp.spec.label}: {rivals}")
    return "\n".join(lines)


def render_correlation(analysis: BroadIndexAnalysis) -> str:
    labels = [sp.spec.label for sp in analysis.sleeve_picks]
    width = max(len(label) for label in labels) + 2
    header = " " * width + "  ".join(label[:6].rjust(6) for label in labels)
    lines = [header]
    for a in labels:
        row_cells = []
        for b in labels:
            value = analysis.correlation.get((a, b))
            row_cells.append("    —" if value is None else f"{value:6.2f}")
        lines.append(f"{a.ljust(width)}" + "  ".join(row_cells))
    return "\n".join(lines)


def write_csv(analysis: BroadIndexAnalysis, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"broad_index_picks_{analysis.as_of:%Y%m%d}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "sleeve",
                "index_code",
                "rank",
                "ts_code",
                "name",
                "management",
                "fee_total_pct",
                "list_date",
                "listing_days",
                "obs_days",
                "avg_daily_amount_60d_cny",
                "return_252d_pct",
                "vol_252d_pct",
                "sharpe_252d",
                "tracking_error_252d_pct",
                "info_ratio_252d",
                "tr_benchmark",
            ]
        )
        for sp in analysis.sleeve_picks:
            entries: list[tuple[int, ETFMetrics]] = []
            if sp.pick is not None:
                entries.append((1, sp.pick))
            for i, m in enumerate(sp.runners_up, start=2):
                entries.append((i, m))
            for rank, m in entries:
                writer.writerow(
                    [
                        sp.spec.label,
                        sp.spec.index_code,
                        rank,
                        m.ts_code,
                        m.name,
                        m.management,
                        f"{m.fee_total_pct:.3f}",
                        m.list_date.isoformat(),
                        m.listing_days,
                        m.obs_days,
                        f"{m.avg_daily_amount_60d:.0f}",
                        _fmt(m.return_252d_pct),
                        _fmt(m.vol_252d_pct),
                        _fmt(m.sharpe_252d),
                        _fmt(m.tracking_error_252d_pct),
                        _fmt(m.info_ratio_252d),
                        "Y" if m.is_total_return_benchmark else "N",
                    ]
                )
    return path


# ----- internals -----


def _metrics_for_etf(
    spec: IndexSpec,
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
    fee = float(universe_row.get("m_fee") or 0.0) + float(universe_row.get("c_fee") or 0.0)
    avg_amount_60d = _mean(amounts[-60:]) * 1000.0  # tushare amount is in ¥thousand

    dated_returns = _dated_returns(series)
    paired = [(d, r, benchmark_returns[d]) for d, r in dated_returns if d in benchmark_returns]
    paired_252 = paired[-252:]
    etf_r = [r for _, r, _ in paired_252]
    bench_r = [b for _, _, b in paired_252]

    return ETFMetrics(
        sleeve=spec.label,
        ts_code=code,
        name=str(universe_row["name"]),
        management=str(universe_row.get("management") or ""),
        list_date=list_date,
        listing_days=listing_days,
        fee_total_pct=fee,
        obs_days=len(series),
        avg_daily_amount_60d=avg_amount_60d,
        return_252d_pct=_period_return_pct(etf_r),
        vol_252d_pct=_annualized_vol_pct(etf_r),
        sharpe_252d=_sharpe(etf_r),
        tracking_error_252d_pct=_tracking_error_pct(etf_r, bench_r),
        info_ratio_252d=_information_ratio(etf_r, bench_r),
        is_total_return_benchmark=spec.is_total_return,
    )


def _rank_sleeve(metrics: list[ETFMetrics]) -> list[ETFMetrics]:
    """For FOF picks among same-index trackers, liquidity dominates among the
    'tight enough' funds: a 10x liquidity advantage beats 40 bps of TE on
    institutional-sized trades. Filter for tight + liquid + seasoned, then
    sort by ADV descending."""
    if not metrics:
        return []
    is_total_return = metrics[0].is_total_return_benchmark
    # On price-index benchmarks the dividend overshoot inflates TE by the
    # sleeve's yield (~3% for 上证50, ~6% for 红利低波), so widen the band.
    te_cap = 1.0 if is_total_return else 8.0
    eligible = [
        m
        for m in metrics
        if m.tracking_error_252d_pct is not None
        and m.tracking_error_252d_pct <= te_cap
        and m.avg_daily_amount_60d >= 1e8
        and m.listing_days >= 252
    ]
    if not eligible:
        eligible = [
            m
            for m in metrics
            if m.tracking_error_252d_pct is not None
            and m.avg_daily_amount_60d >= 3e7
        ]
    if not eligible:
        eligible = [m for m in metrics if m.tracking_error_252d_pct is not None]
    eligible.sort(key=lambda m: (-m.avg_daily_amount_60d, m.fee_total_pct))
    return eligible


def _benchmark_returns_by_code(rows: Sequence[dict[str, Any]]) -> dict[str, dict[date, float]]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_code.setdefault(str(row["ts_code"]), []).append(row)
    out: dict[str, dict[date, float]] = {}
    for code, entries in by_code.items():
        entries.sort(key=lambda r: str(r["trade_date"]))
        prev: float | None = None
        d_returns: dict[date, float] = {}
        for r in entries:
            close = float(r["close"])
            if prev is not None and prev > 0:
                d_returns[_parse_date(str(r["trade_date"]))] = close / prev - 1.0
            prev = close
        out[code] = d_returns
    return out


def _benchmark_correlation(
    by_code: dict[str, dict[date, float]],
    specs: Iterable[IndexSpec],
) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    spec_list = list(specs)
    for a in spec_list:
        ra = by_code.get(a.total_return_code, {})
        for b in spec_list:
            rb = by_code.get(b.total_return_code, {})
            common = sorted(set(ra) & set(rb))[-252:]
            if len(common) < 60:
                out[(a.label, b.label)] = float("nan")
                continue
            xa = [ra[d] for d in common]
            xb = [rb[d] for d in common]
            out[(a.label, b.label)] = _correlation(xa, xb)
    return out


def _correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (n - 1)
    var_x = sum((x - mx) ** 2 for x in xs) / (n - 1)
    var_y = sum((y - my) ** 2 for y in ys) / (n - 1)
    if var_x <= 0 or var_y <= 0:
        return float("nan")
    return cov / math.sqrt(var_x * var_y)


def _dated_returns(series: list[tuple[date, float]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    for i in range(1, len(series)):
        d, close = series[i]
        prev_close = series[i - 1][1]
        if prev_close > 0:
            out.append((d, close / prev_close - 1.0))
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


def _max_benchmark_date(rows: Sequence[dict[str, Any]]) -> date:
    return max(_parse_date(str(r["trade_date"])) for r in rows)


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def _trim(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _fmt(value: float | None, width: int = 0) -> str:
    text = "—" if value is None else f"{value:.2f}"
    return text.rjust(width) if width else text


__all__ = [
    "BROAD_INDEX_SPECS",
    "BroadIndexAnalysis",
    "ETFMetrics",
    "SleevePick",
    "analyze",
    "render_correlation",
    "render_picks",
    "write_csv",
]
