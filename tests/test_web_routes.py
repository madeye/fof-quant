from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fof_quant.web.app import create_app


def _seed_run_dir(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "broad_index_backtest_20240331.json").write_text(
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
                "benchmark_metrics": {
                    "total_return": 0.02,
                    "annualized_return": 0.08,
                    "sharpe": 0.6,
                    "max_drawdown": -0.07,
                },
                "rebalances": [],
                "curve": [
                    {
                        "trade_date": "2024-01-02",
                        "nav": 1.0,
                        "daily_return": 0.0,
                        "drawdown": 0.0,
                    },
                    {
                        "trade_date": "2024-03-31",
                        "nav": 1.04,
                        "daily_return": 0.04,
                        "drawdown": 0.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "broad_index_backtest_20240331.html").write_text(
        "<html><body>backtest report</body></html>", encoding="utf-8"
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    reports_dir = tmp_path / "reports"
    _seed_run_dir(reports_dir)
    app = create_app(reports_dir=reports_dir, db_path=tmp_path / "runs.db", scan_on_boot=True)
    return TestClient(app)


def test_health_includes_run_count(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["runs_count"] == 1


def test_list_runs_returns_summary(client: TestClient) -> None:
    response = client.get("/api/runs")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["kind"] == "broad_index_backtest"
    assert items[0]["as_of_date"] == "2024-03-31"


def test_get_run_includes_metrics(client: TestClient) -> None:
    run_id = client.get("/api/runs").json()[0]["id"]
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["sharpe"] == 1.2
    assert body["benchmark_metrics"]["sharpe"] == 0.6


def test_get_manifest_passthrough(client: TestClient) -> None:
    run_id = client.get("/api/runs").json()[0]["id"]
    response = client.get(f"/api/runs/{run_id}/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["as_of_end"] == "2024-03-31"
    assert len(body["curve"]) == 2


def test_get_report_returns_html(client: TestClient) -> None:
    run_id = client.get("/api/runs").json()[0]["id"]
    response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "backtest report" in response.text


def test_get_run_404(client: TestClient) -> None:
    assert client.get("/api/runs/nope").status_code == 404


def test_post_scan_is_idempotent(client: TestClient) -> None:
    response = client.post("/api/runs/scan")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1


def test_create_run_returns_queued_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    captured: dict[str, object] = {}

    def fake_executor(**kwargs: object) -> None:
        captured.update(kwargs)
        registry = kwargs["registry"]
        run_id = kwargs["run_id"]
        assert isinstance(run_id, str)
        from fof_quant.web.registry import RunRegistry

        assert isinstance(registry, RunRegistry)
        registry.update_status(run_id, "completed")

    monkeypatch.setattr(
        "fof_quant.web.routes.runs.execute_broad_index_backtest", fake_executor
    )
    app = create_app(
        reports_dir=reports_dir,
        cache_dir=cache_dir,
        db_path=tmp_path / "runs.db",
        scan_on_boot=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={
                "kind": "broad_index_backtest",
                "params": {
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-31",
                    "initial_cash": 100000.0,
                    "label": "smoke",
                },
            },
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] in {"queued", "completed"}
        assert body["label"] == "smoke"
        assert body["kind"] == "broad_index_backtest"
        run_id = body["id"]

    assert captured["run_id"] == run_id
    assert (reports_dir / run_id).is_dir()


def test_legacy_backtest_manifest_is_backfilled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    # Legacy manifest: no benchmark_curve, no benchmark_label.
    manifest_path = reports_dir / "broad_index_backtest_20240105.json"
    manifest_path.write_text(
        json.dumps(
            {
                "as_of_start": "2024-01-02",
                "as_of_end": "2024-01-05",
                "metrics": {"sharpe": 1.0},
                "rebalances": [],
                "curve": [
                    {
                        "trade_date": "2024-01-02",
                        "nav": 1.0,
                        "daily_return": 0.0,
                        "drawdown": 0.0,
                    },
                    {
                        "trade_date": "2024-01-03",
                        "nav": 1.005,
                        "daily_return": 0.005,
                        "drawdown": 0.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    fake_series = {
        date(2024, 1, 2): 4000.0,
        date(2024, 1, 3): 4040.0,
    }
    monkeypatch.setattr(
        "fof_quant.web.backfill._benchmark_series",
        lambda label, cache_dir: fake_series,
    )
    app = create_app(
        reports_dir=reports_dir,
        broad_index_cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=True,
    )
    with TestClient(app) as client:
        run_id = client.get("/api/runs").json()[0]["id"]
        body = client.get(f"/api/runs/{run_id}/manifest").json()
    assert body["benchmark_label"] == "沪深300"
    benchmark_curve = body["benchmark_curve"]
    assert len(benchmark_curve) == 2
    assert benchmark_curve[0]["nav"] == 1.0  # base
    assert abs(benchmark_curve[1]["nav"] - 1.01) < 1e-9


def test_create_run_rejects_unknown_kind(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        json={
            "kind": "broad_index_signal",
            "params": {"start_date": "2024-01-02", "end_date": "2024-01-31"},
        },
    )
    assert response.status_code == 422  # pydantic validation rejects unknown literal
