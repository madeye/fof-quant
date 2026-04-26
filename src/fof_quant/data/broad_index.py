from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fof_quant.data.cache import CacheMetadata, CacheStore
from fof_quant.data.datasets import dataset_spec
from fof_quant.data.normalization import normalize_rows
from fof_quant.data.provider import DataRequest, DataTable
from fof_quant.env import tushare_token


@dataclass(frozen=True)
class IndexSpec:
    label: str
    index_code: str
    total_return_code: str
    benchmark_pattern: str  # regex matched against fund_basic.benchmark
    is_total_return: bool = True  # False when total_return_code is actually a price index


BROAD_INDEX_SPECS: tuple[IndexSpec, ...] = (
    IndexSpec("上证50", "000016.SH", "H00016.CSI", r"^上证50指数(收益率)?$"),
    IndexSpec("沪深300", "000300.SH", "H00300.CSI", r"^沪深300指数(收益率)?$"),
    IndexSpec(
        "中证A500",
        "000510.SH",
        "000510.SH",
        r"^中证A500指数(收益率)?$",
        is_total_return=False,
    ),
    IndexSpec("中证500", "000905.SH", "H00905.CSI", r"^中证500指数(收益率)?$"),
    IndexSpec("中证1000", "000852.SH", "H00852.CSI", r"^中证1000指数(收益率)?$"),
    IndexSpec("创业板指", "399006.SZ", "399606.SZ", r"^创业板指数?(收益率)?$"),
    IndexSpec(
        "科创50",
        "000688.SH",
        "000688.SH",
        r"^上证科创板50成份指数(收益率)?$",
        is_total_return=False,
    ),
    IndexSpec(
        "中证红利低波",
        "930955.CSI",
        "930955.CSI",
        r"^中证红利低波动指数(收益率)?$",
        is_total_return=False,
    ),
)


@dataclass(frozen=True)
class BroadIndexFetchResult:
    specs: tuple[IndexSpec, ...]
    universe: DataTable  # one row per ETF, with extra "_sleeve" column
    fund_nav: DataTable
    etf_daily: DataTable
    benchmarks: DataTable  # rows: ts_code (TR or price), trade_date, close


def filter_etfs_for_spec(rows: list[dict[str, Any]], spec: IndexSpec) -> list[dict[str, Any]]:
    pattern = re.compile(spec.benchmark_pattern)
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "L":
            continue
        if row.get("invest_type") != "被动指数型":
            continue
        if "ETF" not in (row.get("name") or ""):
            continue
        if not pattern.match((row.get("benchmark") or "").strip()):
            continue
        out.append({**row, "_sleeve": spec.label})
    return out


def fetch_broad_index(
    *,
    cache_dir: Path,
    start_date: date,
    end_date: date,
    specs: tuple[IndexSpec, ...] = BROAD_INDEX_SPECS,
    sleep: float = 0.4,
    max_etfs_per_sleeve: int = 8,
) -> BroadIndexFetchResult:
    import tushare as ts  # type: ignore[import-untyped]

    token = tushare_token()
    if not token:
        raise ValueError("TUSHARE_TOKEN is not configured")
    pro = ts.pro_api(token)
    cache = CacheStore(cache_dir)
    cache.ensure_dirs()

    universe = _fetch_universe(pro, cache, specs, max_etfs_per_sleeve, start_date, end_date)
    codes = [row["ts_code"] for row in universe.rows]
    fund_nav = _fetch_fund_nav(pro, cache, codes, start_date, end_date, sleep=sleep)
    etf_daily = _fetch_etf_daily(pro, cache, codes, start_date, end_date, sleep=sleep)
    benchmarks = _fetch_benchmarks(pro, cache, specs, start_date, end_date, sleep=sleep)
    return BroadIndexFetchResult(
        specs=specs,
        universe=universe,
        fund_nav=fund_nav,
        etf_daily=etf_daily,
        benchmarks=benchmarks,
    )


def load_broad_index(
    cache_dir: Path,
    specs: tuple[IndexSpec, ...] = BROAD_INDEX_SPECS,
) -> BroadIndexFetchResult:
    cache = CacheStore(cache_dir)
    return BroadIndexFetchResult(
        specs=specs,
        universe=cache.read_table("etf_basic"),
        fund_nav=cache.read_table("fund_nav"),
        etf_daily=cache.read_table("etf_daily"),
        benchmarks=cache.read_table("benchmarks"),
    )


def _fetch_universe(
    pro: Any,
    cache: CacheStore,
    specs: tuple[IndexSpec, ...],
    max_per_sleeve: int,
    start_date: date,
    end_date: date,
) -> DataTable:
    df = pro.fund_basic(market="E", status="L")
    rows = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
    selected: list[dict[str, Any]] = []
    for spec in specs:
        candidates = filter_etfs_for_spec(rows, spec)
        # Pick candidates by listing age (older = more data) capped at max_per_sleeve;
        # we resolve "best" later via liquidity once daily data is loaded.
        candidates.sort(key=lambda r: str(r.get("list_date") or "99999999"))
        selected.extend(candidates[:max_per_sleeve])
    table = normalize_rows(dataset_spec("etf_basic"), selected)
    metadata = CacheMetadata(
        dataset=table.dataset,
        provider="tushare",
        request=DataRequest(
            dataset=table.dataset,
            start_date=start_date,
            end_date=end_date,
            params={"market": "E", "status": "L"},
        ),
        row_count=len(table.rows),
    )
    cache.write_table(table, metadata)
    return table


def _fetch_fund_nav(
    pro: Any,
    cache: CacheStore,
    codes: Iterable[str],
    start_date: date,
    end_date: date,
    *,
    sleep: float,
) -> DataTable:
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    last_call = 0.0
    code_list = list(codes)
    for code in code_list:
        elapsed = time.monotonic() - last_call
        if last_call > 0 and elapsed < sleep:
            time.sleep(sleep - elapsed)
        df = pro.fund_nav(ts_code=code, start_date=start, end_date=end)
        last_call = time.monotonic()
        raw = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
        for row in raw:
            nav_date = row.get("nav_date")
            if not nav_date:
                continue
            key = (code, str(nav_date))
            adj = row.get("adj_nav")
            if key in deduped and deduped[key].get("adj_nav") is not None and adj is None:
                continue
            deduped[key] = {
                "ts_code": code,
                "nav_date": str(nav_date),
                "unit_nav": _to_float(row.get("unit_nav")),
                "accum_nav": _to_float(row.get("accum_nav")),
                "adj_nav": _to_float(adj),
            }
    rows_sorted = sorted(deduped.values(), key=lambda r: (str(r["ts_code"]), str(r["nav_date"])))
    table = DataTable(dataset="fund_nav", rows=rows_sorted)
    metadata = CacheMetadata(
        dataset="fund_nav",
        provider="tushare",
        request=DataRequest(
            dataset="fund_nav",
            start_date=start_date,
            end_date=end_date,
            symbols=code_list,
        ),
        row_count=len(rows_sorted),
    )
    cache.write_table(table, metadata)
    return table


def _fetch_etf_daily(
    pro: Any,
    cache: CacheStore,
    codes: Iterable[str],
    start_date: date,
    end_date: date,
    *,
    sleep: float,
) -> DataTable:
    spec = dataset_spec("etf_daily")
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    rows: list[dict[str, Any]] = []
    last_call = 0.0
    code_list = list(codes)
    for code in code_list:
        elapsed = time.monotonic() - last_call
        if last_call > 0 and elapsed < sleep:
            time.sleep(sleep - elapsed)
        df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)
        last_call = time.monotonic()
        rows.extend(df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df))
    table = normalize_rows(spec, rows)
    metadata = CacheMetadata(
        dataset=spec.name,
        provider="tushare",
        request=DataRequest(
            dataset=spec.name,
            start_date=start_date,
            end_date=end_date,
            symbols=code_list,
        ),
        row_count=len(table.rows),
    )
    cache.write_table(table, metadata)
    return table


def _fetch_benchmarks(
    pro: Any,
    cache: CacheStore,
    specs: tuple[IndexSpec, ...],
    start_date: date,
    end_date: date,
    *,
    sleep: float,
) -> DataTable:
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    rows: list[dict[str, Any]] = []
    last_call = 0.0
    for spec in specs:
        elapsed = time.monotonic() - last_call
        if last_call > 0 and elapsed < sleep:
            time.sleep(sleep - elapsed)
        df = pro.index_daily(ts_code=spec.total_return_code, start_date=start, end_date=end)
        last_call = time.monotonic()
        raw = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
        for r in raw:
            close = _to_float(r.get("close"))
            if close is None:
                continue
            rows.append(
                {
                    "ts_code": spec.total_return_code,
                    "trade_date": str(r["trade_date"]),
                    "close": close,
                }
            )
    rows.sort(key=lambda r: (str(r["ts_code"]), str(r["trade_date"])))
    table = DataTable(dataset="benchmarks", rows=rows)
    metadata = CacheMetadata(
        dataset="benchmarks",
        provider="tushare",
        request=DataRequest(
            dataset="benchmarks",
            start_date=start_date,
            end_date=end_date,
            symbols=[spec.total_return_code for spec in specs],
        ),
        row_count=len(rows),
    )
    cache.write_table(table, metadata)
    return table


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN check
        return None
    return result
