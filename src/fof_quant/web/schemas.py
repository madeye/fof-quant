from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunSummary(BaseModel):
    id: str
    kind: str
    label: str
    as_of_date: str | None
    status: str
    created_at: str
    output_dir: str


class RunDetail(RunSummary):
    manifest_path: str
    report_html_path: str | None
    metrics: dict[str, float] | None = None
    benchmark_metrics: dict[str, float] | None = None


class ScanResponse(BaseModel):
    added: int
    total: int


class HealthResponse(BaseModel):
    ok: bool = True
    runs_count: int


# Generic JSON manifest is returned as `dict[str, Any]` directly; we don't model
# it strictly because the manifest schema differs between signal and backtest
# runs and the frontend handles both branches.
ManifestPayload = dict[str, Any]
