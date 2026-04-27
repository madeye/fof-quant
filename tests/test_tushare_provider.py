from datetime import date
from pathlib import Path
from typing import Any

import pytest

from fof_quant.data.cache import CacheStore
from fof_quant.data.provider import DataRequest
from fof_quant.data.refresh import refresh_datasets
from fof_quant.data.tushare import TushareProvider


class FakeTushareClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def query(self, api_name: str, **params: object) -> list[dict[str, Any]]:
        self.calls.append((api_name, params))
        return [
            {"ts_code": "510300.SH", "trade_date": "20240102", "close": 3.5},
            {"ts_code": "510300.SH", "trade_date": "20240103", "close": 3.6},
        ]


def test_tushare_provider_maps_request_to_api_params() -> None:
    client = FakeTushareClient()
    provider = TushareProvider(client, min_interval_seconds=0, sleep=lambda _: None)

    table = provider.fetch(
        DataRequest(
            dataset="etf_daily",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            symbols=["510300.SH"],
        )
    )

    assert table.dataset == "etf_daily"
    assert len(table.rows) == 2
    assert client.calls == [
        (
            "fund_daily",
            {
                "start_date": "20240101",
                "end_date": "20240131",
                "ts_code": "510300.SH",
            },
        )
    ]


class PerSymbolTushareClient:
    """Returns one row per ts_code, mirroring fund_daily's single-code API."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def query(self, api_name: str, **params: object) -> list[dict[str, Any]]:
        self.calls.append((api_name, params))
        ts_code = params["ts_code"]
        assert isinstance(ts_code, str)
        return [{"ts_code": ts_code, "trade_date": "20240102", "close": 3.5}]


def test_tushare_provider_iterates_per_symbol_when_multiple() -> None:
    client = PerSymbolTushareClient()
    provider = TushareProvider(client, min_interval_seconds=0, sleep=lambda _: None)

    table = provider.fetch(
        DataRequest(
            dataset="etf_daily",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            symbols=["510300.SH", "510500.SH", "159915.SZ"],
        )
    )

    assert {row["ts_code"] for row in table.rows} == {
        "510300.SH",
        "510500.SH",
        "159915.SZ",
    }
    assert [call[1]["ts_code"] for call in client.calls] == [
        "510300.SH",
        "510500.SH",
        "159915.SZ",
    ]


def test_tushare_provider_rejects_unsupported_dataset() -> None:
    provider = TushareProvider(FakeTushareClient(), min_interval_seconds=0)

    with pytest.raises(ValueError, match="unsupported dataset"):
        provider.fetch(DataRequest(dataset="not_real"))


def test_refresh_datasets_writes_cache(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "cache")
    provider = TushareProvider(FakeTushareClient(), min_interval_seconds=0, sleep=lambda _: None)

    metadata = refresh_datasets(
        provider=provider,
        cache=cache,
        requests=[DataRequest(dataset="etf_daily")],
    )

    assert metadata[0].dataset == "etf_daily"
    assert metadata[0].provider == "tushare"
    assert cache.read_table("etf_daily").rows[0]["ts_code"] == "510300.SH"
