from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from fof_quant.web.registry import RunRecord, RunRegistry
from fof_quant.web.scanner import scan_reports_dir
from fof_quant.web.schemas import (
    HealthResponse,
    ManifestPayload,
    RunDetail,
    RunSummary,
    ScanResponse,
)

router = APIRouter(prefix="/api")


def _registry(request: Request) -> RunRegistry:
    registry = request.app.state.registry
    if not isinstance(registry, RunRegistry):
        raise RuntimeError("RunRegistry not configured on app.state")
    return registry


def _reports_dir(request: Request) -> Path:
    return Path(request.app.state.reports_dir)


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
        return _read_manifest(Path(record.manifest_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="manifest file missing") from exc


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


def _to_summary(record: RunRecord) -> RunSummary:
    return RunSummary(
        id=record.id,
        kind=record.kind,
        label=record.label,
        as_of_date=record.as_of_date,
        status=record.status,
        created_at=record.created_at,
        output_dir=record.output_dir,
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
