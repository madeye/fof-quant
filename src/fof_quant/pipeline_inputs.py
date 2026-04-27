from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fof_quant.backtest.engine import PricePoint
from fof_quant.config import AppConfig
from fof_quant.data.cache import CacheStore
from fof_quant.factors.calculators import PriceBar, calculate_price_factors
from fof_quant.factors.exposure import Holding, StockFactor
from fof_quant.universe.eligibility import FundCandidate, UniverseFilter


@dataclass(frozen=True)
class PipelineInputs:
    rebalance_date: date
    candidates: list[FundCandidate]
    fund_holdings: list[Holding]
    index_holdings: list[Holding]
    stock_factors: list[StockFactor]
    etf_prices: list[PricePoint]


def load_pipeline_inputs(config: AppConfig) -> PipelineInputs:
    """Read normalized cache tables and assemble inputs for the offline pipeline.

    Missing tables are treated as empty so the pipeline still runs (with empty
    artifacts) when the cache hasn't been populated. Populating the cache via
    `fof-quant data refresh` produces real factor and backtest outputs.
    """
    cache = CacheStore(config.data.cache_dir)
    etf_basic_rows = _read_rows(cache, "etf_basic")
    fund_portfolio_rows = _read_rows(cache, "fund_portfolio")
    index_weight_rows = _read_rows(cache, "index_weight")
    stock_daily_rows = _read_rows(cache, "stock_daily")
    etf_daily_rows = _read_rows(cache, "etf_daily")

    rebalance_date = (
        config.data.end_date
        or _latest_trade_date(etf_daily_rows)
        or config.data.start_date
    )
    candidates = _candidates_from_etf_basic(
        etf_basic_rows,
        etf_daily_rows,
        as_of_date=rebalance_date,
    )
    fund_holdings = _holdings_from_fund_portfolio(fund_portfolio_rows)
    index_holdings = _holdings_from_index_weight(index_weight_rows, etf_basic_rows)
    price_bars = _price_bars_from_stock_daily(stock_daily_rows)
    stock_factors = (
        calculate_price_factors(price_bars, as_of_date=rebalance_date)
        if price_bars
        else []
    )
    etf_prices = _etf_prices_from_etf_daily(etf_daily_rows)
    return PipelineInputs(
        rebalance_date=rebalance_date,
        candidates=candidates,
        fund_holdings=fund_holdings,
        index_holdings=index_holdings,
        stock_factors=stock_factors,
        etf_prices=etf_prices,
    )


def universe_filter_from_config(config: AppConfig, as_of_date: date) -> UniverseFilter:
    return UniverseFilter(
        allowed_fund_types=set(config.universe.fund_types),
        min_listing_days=config.universe.min_listing_days,
        min_avg_daily_amount=float(config.universe.min_avg_daily_amount),
        min_data_coverage_days=0,
        include=set(config.universe.include),
        exclude=set(config.universe.exclude),
        as_of_date=as_of_date,
    )


def _read_rows(cache: CacheStore, dataset: str) -> list[dict[str, Any]]:
    if not cache.exists(dataset):
        return []
    return list(cache.read_table(dataset).rows)


def _latest_trade_date(etf_daily_rows: list[dict[str, Any]]) -> date | None:
    latest: date | None = None
    for row in etf_daily_rows:
        parsed = _to_date(row.get("trade_date"))
        if parsed is None:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _candidates_from_etf_basic(
    etf_basic_rows: list[dict[str, Any]],
    etf_daily_rows: list[dict[str, Any]],
    *,
    as_of_date: date,
) -> list[FundCandidate]:
    avg_amount, coverage = _liquidity_summary(etf_daily_rows, as_of_date)
    candidates: list[FundCandidate] = []
    for row in etf_basic_rows:
        ts_code = str(row.get("ts_code") or "")
        if not ts_code:
            continue
        list_date = _to_date(row.get("list_date") or row.get("found_date"))
        if list_date is None:
            continue
        candidates.append(
            FundCandidate(
                ts_code=ts_code,
                name=str(row.get("name") or ts_code),
                fund_type=_classify_fund_type(row),
                list_date=list_date,
                status=str(row.get("status") or "L"),
                avg_daily_amount=avg_amount.get(ts_code, 0.0),
                data_coverage_days=coverage.get(ts_code, 0),
            )
        )
    return candidates


def _classify_fund_type(row: dict[str, Any]) -> str:
    """Map raw Tushare fund_basic fields to a coarse fund_type label.

    The default `broad_index_etf` keeps existing configs working when an ETF's
    benchmark text contains the canonical broad-index keywords; everything else
    falls back to `etf`. Configs can opt into the broader bucket by adding `etf`
    to `universe.fund_types`.
    """
    benchmark = str(row.get("benchmark") or row.get("invest_type") or "").upper()
    broad_keywords = ("沪深300", "中证500", "中证800", "中证1000", "上证50", "创业板", "科创")
    if any(keyword.upper() in benchmark for keyword in broad_keywords):
        return "broad_index_etf"
    return "etf"


def _liquidity_summary(
    etf_daily_rows: list[dict[str, Any]], as_of_date: date
) -> tuple[dict[str, float], dict[str, int]]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in etf_daily_rows:
        trade_date = _to_date(row.get("trade_date"))
        if trade_date is None or trade_date > as_of_date:
            continue
        ts_code = str(row.get("ts_code") or "")
        amount = row.get("amount")
        if not ts_code or amount is None:
            continue
        sums[ts_code] = sums.get(ts_code, 0.0) + float(amount)
        counts[ts_code] = counts.get(ts_code, 0) + 1
    avg = {code: sums[code] / counts[code] for code in sums}
    return avg, counts


def _holdings_from_fund_portfolio(rows: list[dict[str, Any]]) -> list[Holding]:
    by_fund_date: dict[tuple[str, date], list[tuple[str, float]]] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        symbol = str(row.get("symbol") or "")
        end_date = _to_date(row.get("end_date"))
        mkv_raw = row.get("mkv")
        if not ts_code or not symbol or end_date is None or mkv_raw is None:
            continue
        try:
            mkv = float(mkv_raw)
        except (TypeError, ValueError):
            continue
        if mkv <= 0:
            continue
        by_fund_date.setdefault((ts_code, end_date), []).append((symbol, mkv))
    holdings: list[Holding] = []
    for (ts_code, end_date), entries in by_fund_date.items():
        total = sum(mkv for _, mkv in entries)
        if total <= 0:
            continue
        for symbol, mkv in entries:
            holdings.append(
                Holding(
                    etf_code=ts_code,
                    stock_code=symbol,
                    weight=mkv / total,
                    as_of_date=end_date,
                    source="fund_portfolio",
                )
            )
    return holdings


def _holdings_from_index_weight(
    index_weight_rows: list[dict[str, Any]],
    etf_basic_rows: list[dict[str, Any]],
) -> list[Holding]:
    """Map index constituents into per-ETF Holdings via ETF benchmark text."""
    available_indices = sorted(
        {str(row.get("index_code") or "") for row in index_weight_rows if row.get("index_code")}
    )
    if not available_indices:
        return []
    etf_to_index = _match_etfs_to_indices(etf_basic_rows, available_indices)
    if not etf_to_index:
        return []
    rows_by_index: dict[str, list[dict[str, Any]]] = {}
    for row in index_weight_rows:
        index_code = str(row.get("index_code") or "")
        if index_code:
            rows_by_index.setdefault(index_code, []).append(row)
    holdings: list[Holding] = []
    for etf_code, index_code in etf_to_index.items():
        for row in rows_by_index.get(index_code, []):
            con_code = str(row.get("con_code") or "")
            weight_raw = row.get("weight")
            trade_date = _to_date(row.get("trade_date"))
            if not con_code or weight_raw is None or trade_date is None:
                continue
            try:
                weight = float(weight_raw)
            except (TypeError, ValueError):
                continue
            holdings.append(
                Holding(
                    etf_code=etf_code,
                    stock_code=con_code,
                    weight=weight,
                    as_of_date=trade_date,
                    source="index_weight",
                )
            )
    return holdings


def _match_etfs_to_indices(
    etf_basic_rows: list[dict[str, Any]],
    index_codes: list[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in etf_basic_rows:
        ts_code = str(row.get("ts_code") or "")
        benchmark = str(row.get("benchmark") or "").upper()
        if not ts_code or not benchmark:
            continue
        for index_code in index_codes:
            short = index_code.split(".")[0].upper()
            if short and short in benchmark:
                mapping[ts_code] = index_code
                break
    return mapping


def _price_bars_from_stock_daily(rows: list[dict[str, Any]]) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for row in rows:
        stock_code = str(row.get("ts_code") or "")
        trade_date = _to_date(row.get("trade_date"))
        close_raw = row.get("close")
        if not stock_code or trade_date is None or close_raw is None:
            continue
        try:
            close = float(close_raw)
        except (TypeError, ValueError):
            continue
        amount_raw = row.get("amount")
        try:
            amount = float(amount_raw) if amount_raw is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0
        bars.append(
            PriceBar(
                stock_code=stock_code,
                trade_date=trade_date,
                close=close,
                amount=amount,
            )
        )
    return bars


def _etf_prices_from_etf_daily(rows: list[dict[str, Any]]) -> list[PricePoint]:
    prices: list[PricePoint] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        trade_date = _to_date(row.get("trade_date"))
        close_raw = row.get("close")
        if not ts_code or trade_date is None or close_raw is None:
            continue
        try:
            close = float(close_raw)
        except (TypeError, ValueError):
            continue
        prices.append(PricePoint(trade_date=trade_date, etf_code=ts_code, close=close))
    return prices


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
