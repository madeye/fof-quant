from __future__ import annotations

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

CSI300_BENCHMARK = "000300.SH"
CSI300_TOTAL_RETURN = "H00300.CSI"
_PURE_BENCHMARKS = frozenset(
    {
        "沪深300指数",
        "沪深300指数收益率",
    }
)


@dataclass(frozen=True)
class CSI300FetchResult:
    universe: DataTable
    etf_daily: DataTable
    index_daily: DataTable
    fund_nav: DataTable
    index_total_return: DataTable


def filter_pure_csi300_etfs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "L":
            continue
        if row.get("invest_type") != "被动指数型":
            continue
        if "ETF" not in (row.get("name") or ""):
            continue
        benchmark = (row.get("benchmark") or "").strip()
        if benchmark not in _PURE_BENCHMARKS:
            continue
        selected.append(row)
    return selected


def fetch_csi300(
    *,
    cache_dir: Path,
    start_date: date,
    end_date: date,
    sleep: float = 0.3,
) -> CSI300FetchResult:
    import tushare as ts  # type: ignore[import-untyped]

    token = tushare_token()
    if not token:
        raise ValueError("TUSHARE_TOKEN is not configured")
    pro = ts.pro_api(token)
    cache = CacheStore(cache_dir)
    cache.ensure_dirs()

    universe = _fetch_universe(pro, cache)
    codes = [row["ts_code"] for row in universe.rows]
    etf_daily = _fetch_etf_daily(pro, cache, codes, start_date, end_date, sleep=sleep)
    index_daily = _fetch_index_daily(pro, cache, start_date, end_date)
    fund_nav = _fetch_fund_nav(pro, cache, codes, start_date, end_date, sleep=sleep)
    index_total_return = _fetch_index_total_return(pro, cache, start_date, end_date)
    return CSI300FetchResult(
        universe=universe,
        etf_daily=etf_daily,
        index_daily=index_daily,
        fund_nav=fund_nav,
        index_total_return=index_total_return,
    )


def load_csi300(cache_dir: Path) -> CSI300FetchResult:
    cache = CacheStore(cache_dir)
    return CSI300FetchResult(
        universe=cache.read_table("etf_basic"),
        etf_daily=cache.read_table("etf_daily"),
        index_daily=cache.read_table("index_daily"),
        fund_nav=cache.read_table("fund_nav"),
        index_total_return=cache.read_table("index_total_return"),
    )


def _fetch_universe(pro: Any, cache: CacheStore) -> DataTable:
    df = pro.fund_basic(market="E", status="L")
    rows = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
    selected = filter_pure_csi300_etfs(rows)
    table = normalize_rows(dataset_spec("etf_basic"), selected)
    metadata = CacheMetadata(
        dataset=table.dataset,
        provider="tushare",
        request=DataRequest(dataset=table.dataset, params={"market": "E", "status": "L"}),
        row_count=len(table.rows),
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
    for code in codes:
        elapsed = time.monotonic() - last_call
        if last_call > 0 and elapsed < sleep:
            time.sleep(sleep - elapsed)
        df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)
        last_call = time.monotonic()
        rows.extend(df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df))
    table = normalize_rows(spec, rows)
    metadata = CacheMetadata(
        dataset=table.dataset,
        provider="tushare",
        request=DataRequest(
            dataset=table.dataset,
            start_date=start_date,
            end_date=end_date,
            symbols=list(codes),
        ),
        row_count=len(table.rows),
    )
    cache.write_table(table, metadata)
    return table


def _fetch_index_daily(
    pro: Any,
    cache: CacheStore,
    start_date: date,
    end_date: date,
) -> DataTable:
    spec = dataset_spec("index_daily")
    df = pro.index_daily(
        ts_code=CSI300_BENCHMARK,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    rows = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
    table = normalize_rows(spec, rows)
    metadata = CacheMetadata(
        dataset=table.dataset,
        provider="tushare",
        request=DataRequest(
            dataset=table.dataset,
            start_date=start_date,
            end_date=end_date,
            symbols=[CSI300_BENCHMARK],
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
    rows_sorted = sorted(deduped.values(), key=lambda r: (r["ts_code"], r["nav_date"]))
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


def _fetch_index_total_return(
    pro: Any,
    cache: CacheStore,
    start_date: date,
    end_date: date,
) -> DataTable:
    df = pro.index_daily(
        ts_code=CSI300_TOTAL_RETURN,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    raw = df.to_dict(orient="records") if hasattr(df, "to_dict") else list(df)
    rows = sorted(
        (
            {
                "ts_code": CSI300_TOTAL_RETURN,
                "trade_date": str(r["trade_date"]),
                "close": _to_float(r.get("close")),
            }
            for r in raw
            if r.get("close") is not None
        ),
        key=lambda r: str(r["trade_date"]),
    )
    table = DataTable(dataset="index_total_return", rows=rows)
    metadata = CacheMetadata(
        dataset="index_total_return",
        provider="tushare",
        request=DataRequest(
            dataset="index_total_return",
            start_date=start_date,
            end_date=end_date,
            symbols=[CSI300_TOTAL_RETURN],
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
