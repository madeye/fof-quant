from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse

from fof_quant.env import llm_env
from fof_quant.web.backfill import synthesize_benchmark_curve
from fof_quant.web.executor import (
    execute_broad_index_backtest,
    execute_broad_index_signal,
)
from fof_quant.web.llm_suggest import LLMSuggestionError, suggest_backtest_params
from fof_quant.web.registry import RunRecord, RunRegistry
from fof_quant.web.scanner import scan_reports_dir
from fof_quant.web.schemas import (
    CreateRunRequest,
    CreateSignalRequest,
    HealthResponse,
    ManifestPayload,
    RunDetail,
    RunSummary,
    ScanResponse,
    SuggestParamsRequest,
    SuggestParamsResponse,
)

router = APIRouter(prefix="/api")


def _registry(request: Request) -> RunRegistry:
    registry = request.app.state.registry
    if not isinstance(registry, RunRegistry):
        raise RuntimeError("RunRegistry not configured on app.state")
    return registry


def _reports_dir(request: Request) -> Path:
    return Path(request.app.state.reports_dir)


def _cache_dir(request: Request) -> Path:
    return Path(request.app.state.cache_dir)


def _broad_index_cache_dir(request: Request) -> Path:
    return Path(request.app.state.broad_index_cache_dir)


def _new_run_id() -> str:
    return uuid.uuid4().hex[:16]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(ok=True, runs_count=_registry(request).count())


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    request: Request,
    kind: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RunSummary]:
    records = _registry(request).list(kind=kind, limit=limit, offset=offset)
    return [_to_summary(r) for r in records]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(request: Request, run_id: str) -> RunDetail:
    record = _registry(request).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    metrics, benchmark = _summary_metrics(record)
    return RunDetail(
        **_to_summary(record).model_dump(),
        manifest_path=record.manifest_path,
        report_html_path=record.report_html_path,
        metrics=metrics,
        benchmark_metrics=benchmark,
    )


@router.get("/runs/{run_id}/manifest", response_model=ManifestPayload)
def get_manifest(request: Request, run_id: str) -> ManifestPayload:
    record = _registry(request).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        manifest = _read_manifest(Path(record.manifest_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="manifest file missing") from exc
    if record.kind == "broad_index_backtest":
        _backfill_benchmark_curve(manifest, _broad_index_cache_dir(request))
    return manifest


def _backfill_benchmark_curve(manifest: dict[str, Any], cache_dir: Path) -> None:
    existing = manifest.get("benchmark_curve")
    if isinstance(existing, list) and existing:
        return
    curve = manifest.get("curve")
    if not isinstance(curve, list) or not curve:
        return
    label = manifest.get("benchmark_label") or "沪深300"
    if not isinstance(label, str):
        label = "沪深300"
    synthesized = synthesize_benchmark_curve(
        strategy_curve=curve,
        benchmark_label=label,
        broad_index_cache_dir=cache_dir,
    )
    if not synthesized:
        return
    manifest["benchmark_curve"] = synthesized
    manifest.setdefault("benchmark_label", label)


@router.get("/runs/{run_id}/report", response_class=HTMLResponse)
def get_report(request: Request, run_id: str) -> HTMLResponse:
    record = _registry(request).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    if record.report_html_path is None:
        raise HTTPException(status_code=404, detail="no html report for this run")
    try:
        html = Path(record.report_html_path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="html report file missing") from exc
    return HTMLResponse(content=html)


@router.post("/runs/scan", response_model=ScanResponse)
def rescan(request: Request) -> ScanResponse:
    registry = _registry(request)
    records = scan_reports_dir(_reports_dir(request))
    added = registry.upsert_many(records)
    return ScanResponse(added=added, total=registry.count())


@router.post("/runs/suggest", response_model=SuggestParamsResponse)
def suggest_params(payload: SuggestParamsRequest) -> SuggestParamsResponse:
    try:
        params = suggest_backtest_params(env=llm_env(), user_prompt=payload.prompt)
    except LLMSuggestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuggestParamsResponse(params=params)


@router.post("/runs", response_model=RunSummary, status_code=202)
def create_run(
    request: Request,
    payload: CreateRunRequest,
    background_tasks: BackgroundTasks,
) -> RunSummary:
    if payload.kind != "broad_index_backtest":
        raise HTTPException(status_code=400, detail=f"unsupported run kind {payload.kind}")
    registry = _registry(request)
    reports_dir = _reports_dir(request)
    # broad_index backtests load via load_broad_index(cache_dir) which expects
    # the broad-index cache layout (etf_basic / fund_nav / etf_daily / benchmarks).
    # The generic --cache-dir tushare cache is irrelevant here.
    cache_dir = _broad_index_cache_dir(request)
    run_id = _new_run_id()
    output_dir = reports_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    label = payload.params.label or (
        f"backtest {payload.params.start_date}→{payload.params.end_date}"
    )
    record = RunRecord(
        id=run_id,
        kind="broad_index_backtest",
        label=label,
        as_of_date=payload.params.end_date,
        output_dir=str(output_dir),
        manifest_path=str(output_dir / "pending.json"),
        report_html_path=None,
        status="queued",
        created_at=datetime.now(tz=UTC).isoformat(),
        config_yaml=payload.model_dump_json(indent=2),
    )
    registry.upsert_many([record])
    background_tasks.add_task(
        execute_broad_index_backtest,
        registry=registry,
        run_id=run_id,
        cache_dir=cache_dir,
        output_dir=output_dir,
        params=payload.params,
    )
    return _to_summary(record)


@router.post("/runs/signal", response_model=RunSummary, status_code=202)
def create_signal_run(
    request: Request,
    payload: CreateSignalRequest,
    background_tasks: BackgroundTasks,
) -> RunSummary:
    """Trigger today's broad-index trading signal.

    Uses the broad-index cache (same data the existing CLI signal pipeline
    reads). Optional current holdings are written to a per-run holdings.json
    so the rebalance line is computed against real positions.
    """
    registry = _registry(request)
    reports_dir = _reports_dir(request)
    broad_index_cache_dir = _broad_index_cache_dir(request)
    run_id = _new_run_id()
    output_dir = reports_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    label = payload.params.label or "当日信号"
    record = RunRecord(
        id=run_id,
        kind="broad_index_signal",
        label=label,
        as_of_date=None,
        output_dir=str(output_dir),
        manifest_path=str(output_dir / "pending.json"),
        report_html_path=None,
        status="queued",
        created_at=datetime.now(tz=UTC).isoformat(),
        config_yaml=payload.model_dump_json(indent=2),
    )
    registry.upsert_many([record])
    background_tasks.add_task(
        execute_broad_index_signal,
        registry=registry,
        run_id=run_id,
        cache_dir=broad_index_cache_dir,
        output_dir=output_dir,
        params=payload.params,
    )
    return _to_summary(record)


def _to_summary(record: RunRecord) -> RunSummary:
    return RunSummary(
        id=record.id,
        kind=record.kind,
        label=record.label,
        as_of_date=record.as_of_date,
        status=record.status,
        created_at=record.created_at,
        output_dir=record.output_dir,
        error=record.error,
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest at {path} is not a JSON object")
    return payload


def _summary_metrics(
    record: RunRecord,
) -> tuple[dict[str, float] | None, dict[str, float] | None]:
    if record.kind != "broad_index_backtest":
        return None, None
    try:
        payload = _read_manifest(Path(record.manifest_path))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return None, None
    metrics = payload.get("metrics") if isinstance(payload, dict) else None
    benchmark = payload.get("benchmark_metrics") if isinstance(payload, dict) else None
    return _coerce_metrics(metrics), _coerce_metrics(benchmark)


def _coerce_metrics(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, float] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return out or None
