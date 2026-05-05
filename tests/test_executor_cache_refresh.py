from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fof_quant.web.executor import (
    execute_broad_index_backtest,
    execute_broad_index_signal,
)
from fof_quant.web.registry import RunRecord, RunRegistry
from fof_quant.web.schemas import BroadIndexBacktestParams, BroadIndexSignalParams


def _seed_run(registry: RunRegistry, run_id: str, kind: str, output_dir: Path) -> None:
    registry.upsert_many(
        [
            RunRecord(
                id=run_id,
                kind=kind,
                label="test",
                as_of_date=None,
                output_dir=str(output_dir),
                manifest_path=str(output_dir / "pending.json"),
                report_html_path=None,
                status="queued",
                created_at=datetime.now(tz=UTC).isoformat(),
            )
        ]
    )


def test_backtest_marks_run_failed_when_cache_refresh_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    run_id = "r1"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    _seed_run(registry, run_id, "broad_index_backtest", output_dir)

    def boom(*_: object, **__: object) -> object:
        raise ValueError("TUSHARE_TOKEN is not configured")

    monkeypatch.setattr("fof_quant.web.executor.ensure_broad_index_cache_fresh", boom)

    def must_not_run(**_: object) -> object:  # pragma: no cover
        raise AssertionError("pipeline should not run after cache refresh failure")

    monkeypatch.setattr(
        "fof_quant.pipeline_broad_index.run_broad_index_backtest_pipeline", must_not_run
    )

    execute_broad_index_backtest(
        registry=registry,
        run_id=run_id,
        cache_dir=tmp_path / "cache",
        output_dir=output_dir,
        params=BroadIndexBacktestParams(start_date="2024-01-02", end_date="2024-01-31"),
    )

    record = registry.get(run_id)
    assert record is not None
    assert record.status == "failed"
    assert record.error is not None
    assert "TUSHARE_TOKEN" in record.error


def test_signal_marks_run_failed_when_cache_refresh_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    run_id = "s1"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    _seed_run(registry, run_id, "broad_index_signal", output_dir)

    def boom(*_: object, **__: object) -> object:
        raise RuntimeError("network down")

    monkeypatch.setattr("fof_quant.web.executor.ensure_broad_index_cache_fresh", boom)

    def must_not_run(**_: object) -> object:  # pragma: no cover
        raise AssertionError("pipeline should not run after cache refresh failure")

    monkeypatch.setattr(
        "fof_quant.pipeline_broad_index.run_broad_index_pipeline", must_not_run
    )

    execute_broad_index_signal(
        registry=registry,
        run_id=run_id,
        cache_dir=tmp_path / "cache",
        output_dir=output_dir,
        params=BroadIndexSignalParams(),
    )

    record = registry.get(run_id)
    assert record is not None
    assert record.status == "failed"
    assert record.error is not None
    assert "network down" in record.error


def test_signal_calls_cache_refresh_before_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    run_id = "s2"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    _seed_run(registry, run_id, "broad_index_signal", output_dir)

    order: list[str] = []

    def fake_refresh(*_: object, **__: object) -> bool:
        order.append("refresh")
        return False

    def fake_pipeline(**_: object) -> object:
        order.append("pipeline")
        raise RuntimeError("stop after order check")

    monkeypatch.setattr(
        "fof_quant.web.executor.ensure_broad_index_cache_fresh", fake_refresh
    )
    monkeypatch.setattr(
        "fof_quant.pipeline_broad_index.run_broad_index_pipeline", fake_pipeline
    )

    execute_broad_index_signal(
        registry=registry,
        run_id=run_id,
        cache_dir=tmp_path / "cache",
        output_dir=output_dir,
        params=BroadIndexSignalParams(),
    )

    assert order == ["refresh", "pipeline"]
