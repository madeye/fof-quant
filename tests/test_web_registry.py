from __future__ import annotations

import json
from pathlib import Path

from fof_quant.web.registry import RunRegistry
from fof_quant.web.scanner import scan_reports_dir


def _seed_artifacts(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    rebalance = reports_dir / "broad_index_rebalance_20240105.json"
    rebalance.write_text(
        json.dumps(
            {
                "as_of": "2024-01-05",
                "total_aum_cny": 1_000_000.0,
                "rebalance_lines": [],
                "trade_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "broad_index_signal_20240105.html").write_text(
        "<html><body>signal</body></html>", encoding="utf-8"
    )
    backtest = reports_dir / "broad_index_backtest_20240331.json"
    backtest.write_text(
        json.dumps(
            {
                "as_of_start": "2024-01-02",
                "as_of_end": "2024-03-31",
                "metrics": {
                    "total_return": 0.04,
                    "annualized_return": 0.16,
                    "sharpe": 1.2,
                    "max_drawdown": -0.05,
                },
                "rebalances": [],
                "curve": [],
            }
        ),
        encoding="utf-8",
    )


def test_scan_picks_up_signal_and_backtest(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _seed_artifacts(reports_dir)

    records = scan_reports_dir(reports_dir)

    by_kind = {r.kind: r for r in records}
    assert set(by_kind) == {"broad_index_signal", "broad_index_backtest"}
    signal = by_kind["broad_index_signal"]
    assert signal.as_of_date == "2024-01-05"
    assert signal.report_html_path is not None
    assert Path(signal.report_html_path).name == "broad_index_signal_20240105.html"
    backtest = by_kind["broad_index_backtest"]
    assert backtest.as_of_date == "2024-03-31"
    assert backtest.report_html_path is None  # html not seeded for backtest


def test_registry_upsert_is_idempotent(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _seed_artifacts(reports_dir)
    registry = RunRegistry(tmp_path / "runs.db")
    records = scan_reports_dir(reports_dir)

    registry.upsert_many(records)
    first_count = registry.count()
    registry.upsert_many(records)
    second_count = registry.count()

    assert first_count == 2
    assert second_count == 2  # upsert, not insert


def test_registry_list_orders_newest_first(tmp_path: Path) -> None:
    import os

    reports_dir = tmp_path / "reports"
    _seed_artifacts(reports_dir)
    rebalance_path = reports_dir / "broad_index_rebalance_20240105.json"
    backtest_path = reports_dir / "broad_index_backtest_20240331.json"
    os.utime(rebalance_path, (1_700_000_000, 1_700_000_000))
    os.utime(backtest_path, (1_710_000_000, 1_710_000_000))
    registry = RunRegistry(tmp_path / "runs.db")
    registry.upsert_many(scan_reports_dir(reports_dir))

    listed = registry.list()

    assert listed[0].kind == "broad_index_backtest"
