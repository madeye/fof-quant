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


def test_suggest_params_returns_validated_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fof_quant.web.schemas import BroadIndexBacktestParams

    fake = BroadIndexBacktestParams(
        start_date="2022-01-04",
        end_date="2025-04-26",
        initial_cash=500_000,
        sleeve_weights={"中证A500": 0.5, "中证红利低波": 0.5},
        cash_buffer=0.0,
        max_weight=0.6,
        abs_band_pp=4.0,
        rel_band_pct=20.0,
        transaction_cost_bps=2.0,
        slippage_bps=1.0,
        benchmark_label="沪深300",
        label="低波防守",
    )
    monkeypatch.setattr(
        "fof_quant.web.routes.runs.suggest_backtest_params",
        lambda env, user_prompt: fake,
    )
    app = create_app(
        reports_dir=tmp_path / "reports",
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/runs/suggest",
            json={"prompt": "我想做一个稳健的低波回测，时间 3 年。"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["params"]["label"] == "低波防守"
    assert body["params"]["sleeve_weights"]["中证A500"] == 0.5


def test_suggest_params_surfaces_llm_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fof_quant.web.llm_suggest import LLMSuggestionError

    def _raise(env: object, user_prompt: str) -> object:
        raise LLMSuggestionError("LLM 未配置：请先设置 LLM_API_KEY。")

    monkeypatch.setattr("fof_quant.web.routes.runs.suggest_backtest_params", _raise)
    app = create_app(
        reports_dir=tmp_path / "reports",
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=False,
    )
    with TestClient(app) as client:
        response = client.post("/api/runs/suggest", json={"prompt": "防守"})
    assert response.status_code == 400
    assert "LLM" in response.json()["detail"]


def test_create_run_rejects_unknown_kind(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        json={
            "kind": "broad_index_signal",
            "params": {"start_date": "2024-01-02", "end_date": "2024-01-31"},
        },
    )
    assert response.status_code == 422  # pydantic validation rejects unknown literal


# ---------------------------------------------------------------------------
# Listing / filtering / paging
# ---------------------------------------------------------------------------


def _seed_two_kinds(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "broad_index_backtest_20240331.json").write_text(
        json.dumps({"metrics": {}, "rebalances": [], "curve": []}),
        encoding="utf-8",
    )
    (reports_dir / "broad_index_rebalance_20240105.json").write_text(
        json.dumps(
            {
                "as_of": "2024-01-05",
                "total_aum_cny": 100_000.0,
                "rebalance_lines": [],
                "trade_count": 0,
            }
        ),
        encoding="utf-8",
    )


def test_list_runs_filters_by_kind(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _seed_two_kinds(reports_dir)
    app = create_app(
        reports_dir=reports_dir, db_path=tmp_path / "runs.db", scan_on_boot=True
    )
    with TestClient(app) as client:
        all_kinds = {r["kind"] for r in client.get("/api/runs").json()}
        backtests = client.get("/api/runs?kind=broad_index_backtest").json()
        signals = client.get("/api/runs?kind=broad_index_signal").json()
    assert all_kinds == {"broad_index_backtest", "broad_index_signal"}
    assert len(backtests) == 1
    assert backtests[0]["kind"] == "broad_index_backtest"
    assert len(signals) == 1
    assert signals[0]["kind"] == "broad_index_signal"


def test_list_runs_pagination(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _seed_two_kinds(reports_dir)
    app = create_app(
        reports_dir=reports_dir, db_path=tmp_path / "runs.db", scan_on_boot=True
    )
    with TestClient(app) as client:
        first = client.get("/api/runs?limit=1&offset=0").json()
        second = client.get("/api/runs?limit=1&offset=1").json()
    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["id"] != second[0]["id"]


# ---------------------------------------------------------------------------
# Manifest / report error paths
# ---------------------------------------------------------------------------


def test_manifest_returns_410_when_file_deleted_underneath(client: TestClient) -> None:
    summary = client.get("/api/runs").json()[0]
    Path(summary["output_dir"], "broad_index_backtest_20240331.json").unlink()
    response = client.get(f"/api/runs/{summary['id']}/manifest")
    assert response.status_code == 410


def test_report_returns_404_when_run_has_no_html(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    # Manifest only — no companion HTML.
    (reports_dir / "broad_index_backtest_20240331.json").write_text(
        json.dumps({"metrics": {}, "rebalances": [], "curve": []}),
        encoding="utf-8",
    )
    app = create_app(
        reports_dir=reports_dir, db_path=tmp_path / "runs.db", scan_on_boot=True
    )
    with TestClient(app) as client:
        run_id = client.get("/api/runs").json()[0]["id"]
        response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Signal trigger
# ---------------------------------------------------------------------------


def test_create_signal_run_writes_holdings_to_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    captured: dict[str, object] = {}

    # Stub the executor with a function that exercises the holdings.json
    # write path that the real executor performs, so we can assert the
    # file lands in the per-run subdir without needing the broad-index cache.
    def fake_executor_with_io(**kwargs: object) -> None:
        from fof_quant.web.registry import RunRegistry
        from fof_quant.web.schemas import BroadIndexSignalParams

        params = kwargs["params"]
        output_dir = kwargs["output_dir"]
        assert isinstance(params, BroadIndexSignalParams)
        assert isinstance(output_dir, Path)
        if params.holdings is not None:
            (output_dir / "holdings.json").write_text(
                json.dumps(params.holdings, ensure_ascii=False), encoding="utf-8"
            )
        registry = kwargs["registry"]
        run_id = kwargs["run_id"]
        assert isinstance(registry, RunRegistry)
        assert isinstance(run_id, str)
        registry.update_status(run_id, "completed")
        captured["called"] = True

    monkeypatch.setattr(
        "fof_quant.web.routes.runs.execute_broad_index_signal", fake_executor_with_io
    )
    app = create_app(
        reports_dir=reports_dir,
        broad_index_cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/runs/signal",
            json={
                "params": {
                    "label": "smoke signal",
                    "holdings": {
                        "as_of": "2024-04-01",
                        "cash_cny": 50_000,
                        "positions": [{"ts_code": "510300.SH", "shares": 100_000}],
                    },
                    "initial_cash_if_empty": 1_000_000.0,
                    "cash_buffer": 0.01,
                    "max_weight": 0.4,
                    "abs_band_pp": 5.0,
                    "rel_band_pct": 25.0,
                    "force_rebalance": False,
                },
            },
        )
    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "broad_index_signal"
    assert body["label"] == "smoke signal"
    assert captured.get("called") is True
    persisted = reports_dir / body["id"] / "holdings.json"
    assert persisted.exists()
    assert json.loads(persisted.read_text(encoding="utf-8"))["cash_cny"] == 50_000


def test_create_signal_run_uses_default_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fof_quant.web.routes.runs.execute_broad_index_signal",
        lambda **kwargs: None,
    )
    app = create_app(
        reports_dir=tmp_path / "reports",
        broad_index_cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=False,
    )
    with TestClient(app) as client:
        response = client.post("/api/runs/signal", json={})
    assert response.status_code == 202
    assert response.json()["label"] == "当日信号"


# ---------------------------------------------------------------------------
# Backfill edge cases
# ---------------------------------------------------------------------------


def test_backfill_preserves_existing_benchmark_curve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    # Manifest already carries benchmark_curve — backfill must not overwrite.
    (reports_dir / "broad_index_backtest_20240105.json").write_text(
        json.dumps(
            {
                "metrics": {},
                "rebalances": [],
                "curve": [
                    {"trade_date": "2024-01-02", "nav": 1.0, "daily_return": 0, "drawdown": 0}
                ],
                "benchmark_curve": [
                    {"trade_date": "2024-01-02", "nav": 9.99, "daily_return": 0, "drawdown": 0}
                ],
                "benchmark_label": "原始基准",
            }
        ),
        encoding="utf-8",
    )
    # Series loader would return non-trivial data — but we should never call it.
    called = {"loader": False}

    def fake_loader(label: object, cache_dir: object) -> dict[date, float]:
        called["loader"] = True
        return {date(2024, 1, 2): 1234.0}

    monkeypatch.setattr("fof_quant.web.backfill._benchmark_series", fake_loader)
    app = create_app(
        reports_dir=reports_dir,
        broad_index_cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=True,
    )
    with TestClient(app) as client:
        run_id = client.get("/api/runs").json()[0]["id"]
        body = client.get(f"/api/runs/{run_id}/manifest").json()
    assert body["benchmark_label"] == "原始基准"
    assert body["benchmark_curve"][0]["nav"] == 9.99
    assert called["loader"] is False


def test_backfill_no_op_when_cache_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "broad_index_backtest_20240105.json").write_text(
        json.dumps(
            {
                "metrics": {},
                "rebalances": [],
                "curve": [
                    {"trade_date": "2024-01-02", "nav": 1.0, "daily_return": 0, "drawdown": 0}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fof_quant.web.backfill._benchmark_series",
        lambda label, cache_dir: {},
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
    # No benchmark_curve added; route returns the manifest as-is.
    assert "benchmark_curve" not in body or not body["benchmark_curve"]


def test_backfill_skipped_for_signal_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "broad_index_rebalance_20240105.json").write_text(
        json.dumps(
            {
                "as_of": "2024-01-05",
                "total_aum_cny": 0.0,
                "rebalance_lines": [],
                "trade_count": 0,
            }
        ),
        encoding="utf-8",
    )
    called = {"loader": False}

    def fake_loader(label: object, cache_dir: object) -> dict[date, float]:
        called["loader"] = True
        return {}

    monkeypatch.setattr("fof_quant.web.backfill._benchmark_series", fake_loader)
    app = create_app(
        reports_dir=reports_dir,
        broad_index_cache_dir=tmp_path / "cache",
        db_path=tmp_path / "runs.db",
        scan_on_boot=True,
    )
    with TestClient(app) as client:
        run_id = client.get("/api/runs").json()[0]["id"]
        client.get(f"/api/runs/{run_id}/manifest")
    assert called["loader"] is False  # only broad_index_backtest triggers backfill
