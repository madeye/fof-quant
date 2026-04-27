"""Lazy backfill helpers for legacy manifests that lack newer fields.

Backtest manifests written before the dashboard exposed `benchmark_curve`
(see PR #24) only carry the strategy curve. Re-running every legacy run is
cheap but disruptive; instead, the API synthesizes the missing benchmark
curve on demand by reading the cached benchmark prices and walking them
across the strategy curve dates.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def synthesize_benchmark_curve(
    *,
    strategy_curve: list[dict[str, Any]],
    benchmark_label: str,
    broad_index_cache_dir: Path,
) -> list[dict[str, Any]]:
    """Build a benchmark NAV curve from cached broad-index data.

    Returns an empty list if the cache is missing, the benchmark label is
    unknown, or the curve dates can't be matched. Mirrors
    ``backtest_broad_index._benchmark_curve`` so the synthesized output is
    indistinguishable from a freshly-emitted manifest.
    """
    if not strategy_curve:
        return []
    dates = _dates_from_curve(strategy_curve)
    if not dates:
        return []
    series = _benchmark_series(benchmark_label, broad_index_cache_dir)
    if not series:
        return []
    base = next((series[d] for d in dates if d in series), None)
    if base is None or base <= 0:
        return []
    out: list[dict[str, Any]] = []
    peak = base
    prev = base
    for d in dates:
        v = series.get(d, prev)
        ret = v / prev - 1.0 if out else 0.0
        peak = max(peak, v)
        dd = v / peak - 1.0
        out.append(
            {
                "trade_date": d.isoformat(),
                "nav": v / base,
                "daily_return": ret,
                "drawdown": dd,
            }
        )
        prev = v
    return out


def _dates_from_curve(curve: list[dict[str, Any]]) -> list[date]:
    dates: list[date] = []
    for point in curve:
        raw = point.get("trade_date")
        if not isinstance(raw, str):
            continue
        try:
            dates.append(datetime.strptime(raw, "%Y-%m-%d").date())
        except ValueError:
            continue
    return dates


def _benchmark_series(benchmark_label: str, cache_dir: Path) -> dict[date, float]:
    """Load the cached benchmark prices for the labeled index.

    Imports the broad-index data layer lazily so the backfill module stays
    importable even when no cache exists (e.g. in unit tests).
    """
    try:
        from fof_quant.data.broad_index import BROAD_INDEX_SPECS, load_broad_index
    except ImportError:  # pragma: no cover - import guard
        return {}
    spec = next((s for s in BROAD_INDEX_SPECS if s.label == benchmark_label), None)
    if spec is None:
        return {}
    try:
        fetched = load_broad_index(cache_dir)
    except (FileNotFoundError, OSError, ValueError) as exc:
        logger.debug("benchmark backfill skipped: %s", exc)
        return {}
    series: dict[date, float] = {}
    for row in fetched.benchmarks.rows:
        if str(row.get("ts_code")) != spec.total_return_code:
            continue
        trade_date = str(row.get("trade_date"))
        try:
            parsed = datetime.strptime(trade_date, "%Y%m%d").date()
        except ValueError:
            try:
                parsed = datetime.strptime(trade_date, "%Y-%m-%d").date()
            except ValueError:
                continue
        close = row.get("close")
        if close is None:
            continue
        try:
            series[parsed] = float(close)
        except (TypeError, ValueError):
            continue
    return series
