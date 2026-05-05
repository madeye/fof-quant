from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from fof_quant.data.broad_index import (
    BROAD_INDEX_DATASETS,
    DEFAULT_BROAD_INDEX_START,
    ensure_broad_index_cache_fresh,
)
from fof_quant.data.cache import CacheMetadata, CacheStore, is_cache_stale
from fof_quant.data.provider import DataRequest, DataTable


def _seed_dataset(
    store: CacheStore, dataset: str, *, fetched_at: datetime, start_date: date | None = None
) -> None:
    table = DataTable(dataset=dataset, rows=[])
    metadata = CacheMetadata(
        dataset=dataset,
        provider="tushare",
        fetched_at=fetched_at,
        request=DataRequest(dataset=dataset, start_date=start_date),
        row_count=0,
    )
    store.write_table(table, metadata)


def test_is_cache_stale_when_dataset_missing(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    assert is_cache_stale(store, BROAD_INDEX_DATASETS) is True


def test_is_cache_stale_when_older_than_one_day(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    stale = now - timedelta(days=1, seconds=1)
    for dataset in BROAD_INDEX_DATASETS:
        _seed_dataset(store, dataset, fetched_at=stale)
    assert is_cache_stale(store, BROAD_INDEX_DATASETS, now=now) is True


def test_is_cache_fresh_within_one_day(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    fresh = now - timedelta(hours=23)
    for dataset in BROAD_INDEX_DATASETS:
        _seed_dataset(store, dataset, fetched_at=fresh)
    assert is_cache_stale(store, BROAD_INDEX_DATASETS, now=now) is False


def test_is_cache_stale_when_one_dataset_lags(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    fresh = now - timedelta(hours=1)
    stale = now - timedelta(days=2)
    for dataset in BROAD_INDEX_DATASETS[:-1]:
        _seed_dataset(store, dataset, fetched_at=fresh)
    _seed_dataset(store, BROAD_INDEX_DATASETS[-1], fetched_at=stale)
    assert is_cache_stale(store, BROAD_INDEX_DATASETS, now=now) is True


def test_ensure_broad_index_cache_fresh_skips_when_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CacheStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    fresh = now - timedelta(hours=1)
    for dataset in BROAD_INDEX_DATASETS:
        _seed_dataset(store, dataset, fetched_at=fresh)

    def fail_fetch(**_: object) -> object:  # pragma: no cover - must not be called
        raise AssertionError("fetch_broad_index should not run when cache is fresh")

    monkeypatch.setattr("fof_quant.data.broad_index.fetch_broad_index", fail_fetch)
    refreshed = ensure_broad_index_cache_fresh(tmp_path, now=now)
    assert refreshed is False


def test_ensure_broad_index_cache_fresh_refetches_when_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CacheStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    stale = now - timedelta(days=2)
    for dataset in BROAD_INDEX_DATASETS:
        _seed_dataset(
            store, dataset, fetched_at=stale, start_date=date(2020, 6, 1)
        )

    captured: dict[str, object] = {}

    def fake_fetch(**kwargs: object) -> object:
        captured.update(kwargs)
        return None

    monkeypatch.setattr("fof_quant.data.broad_index.fetch_broad_index", fake_fetch)

    refreshed = ensure_broad_index_cache_fresh(
        tmp_path, end_date=now.date(), now=now
    )
    assert refreshed is True
    assert captured["cache_dir"] == tmp_path
    assert captured["start_date"] == date(2020, 6, 1)
    assert captured["end_date"] == now.date()


def test_ensure_broad_index_cache_fresh_uses_default_start_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(**kwargs: object) -> object:
        captured.update(kwargs)
        return None

    monkeypatch.setattr("fof_quant.data.broad_index.fetch_broad_index", fake_fetch)
    refreshed = ensure_broad_index_cache_fresh(tmp_path)
    assert refreshed is True
    assert captured["start_date"] == DEFAULT_BROAD_INDEX_START


def test_ensure_broad_index_cache_fresh_propagates_fetch_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_: object) -> object:
        raise ValueError("TUSHARE_TOKEN is not configured")

    monkeypatch.setattr("fof_quant.data.broad_index.fetch_broad_index", boom)
    with pytest.raises(ValueError, match="TUSHARE_TOKEN"):
        ensure_broad_index_cache_fresh(tmp_path)
