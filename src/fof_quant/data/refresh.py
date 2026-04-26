from __future__ import annotations

from fof_quant.data.cache import CacheMetadata, CacheStore
from fof_quant.data.provider import DataProvider, DataRequest

DEFAULT_DATASETS = (
    "trade_calendar",
    "etf_basic",
    "etf_daily",
    "fund_nav",
    "index_daily",
    "index_weight",
    "fund_portfolio",
)


def refresh_datasets(
    *,
    provider: DataProvider,
    cache: CacheStore,
    requests: list[DataRequest],
) -> list[CacheMetadata]:
    metadata: list[CacheMetadata] = []
    for request in requests:
        table = provider.fetch(request)
        item = CacheMetadata(
            dataset=table.dataset,
            provider=provider.name,
            request=request,
            row_count=len(table.rows),
        )
        cache.write_table(table, item)
        metadata.append(item)
    return metadata
