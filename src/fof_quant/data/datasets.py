from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    tushare_api: str
    required_fields: frozenset[str]
    unique_key: tuple[str, ...]
    date_field: str | None = None
    symbol_field: str | None = None


DATASETS: dict[str, DatasetSpec] = {
    "trade_calendar": DatasetSpec(
        name="trade_calendar",
        tushare_api="trade_cal",
        required_fields=frozenset({"cal_date", "is_open"}),
        unique_key=("cal_date",),
        date_field="cal_date",
    ),
    "etf_basic": DatasetSpec(
        name="etf_basic",
        tushare_api="fund_basic",
        required_fields=frozenset({"ts_code", "name"}),
        unique_key=("ts_code",),
        symbol_field="ts_code",
    ),
    "etf_daily": DatasetSpec(
        name="etf_daily",
        tushare_api="fund_daily",
        required_fields=frozenset({"ts_code", "trade_date", "close"}),
        unique_key=("ts_code", "trade_date"),
        date_field="trade_date",
        symbol_field="ts_code",
    ),
    "fund_nav": DatasetSpec(
        name="fund_nav",
        tushare_api="fund_nav",
        required_fields=frozenset({"ts_code", "end_date", "unit_nav"}),
        unique_key=("ts_code", "end_date"),
        date_field="end_date",
        symbol_field="ts_code",
    ),
    "index_daily": DatasetSpec(
        name="index_daily",
        tushare_api="index_daily",
        required_fields=frozenset({"ts_code", "trade_date", "close"}),
        unique_key=("ts_code", "trade_date"),
        date_field="trade_date",
        symbol_field="ts_code",
    ),
    "index_weight": DatasetSpec(
        name="index_weight",
        tushare_api="index_weight",
        required_fields=frozenset({"index_code", "con_code", "trade_date", "weight"}),
        unique_key=("index_code", "con_code", "trade_date"),
        date_field="trade_date",
        symbol_field="index_code",
    ),
    "fund_portfolio": DatasetSpec(
        name="fund_portfolio",
        tushare_api="fund_portfolio",
        required_fields=frozenset({"ts_code", "symbol", "end_date", "mkv"}),
        unique_key=("ts_code", "symbol", "end_date"),
        date_field="end_date",
        symbol_field="ts_code",
    ),
}


def dataset_spec(name: str) -> DatasetSpec:
    try:
        return DATASETS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(DATASETS))
        raise ValueError(f"unsupported dataset {name!r}; supported datasets: {supported}") from exc
