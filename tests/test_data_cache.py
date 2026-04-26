from datetime import date
from pathlib import Path

import pytest

from fof_quant.data.cache import CacheMetadata, CacheStore
from fof_quant.data.provider import DataRequest, DataTable


def test_cache_store_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    store = CacheStore(root)
    request = DataRequest(dataset="etf_daily", start_date=date(2024, 1, 1))
    table = DataTable(
        dataset="etf_daily",
        rows=[
            {"ts_code": "510300.SH", "trade_date": "2024-01-02", "close": 3.5},
        ],
    )
    metadata = CacheMetadata(
        dataset="etf_daily",
        provider="tushare",
        request=request,
        row_count=len(table.rows),
    )

    store.write_table(table, metadata)

    assert store.exists("etf_daily")
    assert store.read_table("etf_daily") == table
    assert store.read_metadata("etf_daily").row_count == 1


def test_table_required_field_validation() -> None:
    table = DataTable(dataset="etf_daily", rows=[{"ts_code": "510300.SH"}])

    with pytest.raises(ValueError, match="missing required fields"):
        table.validate_required_fields({"ts_code", "trade_date"})


def test_table_unique_key_validation() -> None:
    table = DataTable(
        dataset="etf_daily",
        rows=[
            {"ts_code": "510300.SH", "trade_date": "2024-01-02"},
            {"ts_code": "510300.SH", "trade_date": "2024-01-02"},
        ],
    )

    with pytest.raises(ValueError, match="duplicate keys"):
        table.validate_unique_key(("ts_code", "trade_date"))
