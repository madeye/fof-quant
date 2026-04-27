from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    id: str
    kind: str
    label: str
    as_of_date: str | None
    status: str
    created_at: str
    output_dir: str
    error: str | None = None


class RunDetail(RunSummary):
    manifest_path: str
    report_html_path: str | None
    metrics: dict[str, float] | None = None
    benchmark_metrics: dict[str, float] | None = None


class BroadIndexBacktestParams(BaseModel):
    start_date: str = Field(description="ISO yyyy-mm-dd")
    end_date: str = Field(description="ISO yyyy-mm-dd")
    initial_cash: float = Field(default=1_000_000.0, gt=0)
    sleeve_weights: dict[str, float] | None = None
    cash_buffer: float = Field(default=0.01, ge=0.0, lt=1.0)
    max_weight: float = Field(default=0.4, gt=0.0, le=1.0)
    abs_band_pp: float = Field(default=5.0, ge=0.0)
    rel_band_pct: float = Field(default=25.0, ge=0.0)
    transaction_cost_bps: float = Field(default=2.0, ge=0.0)
    slippage_bps: float = Field(default=1.0, ge=0.0)
    benchmark_label: str = "沪深300"
    label: str | None = None


class CreateRunRequest(BaseModel):
    kind: Literal["broad_index_backtest"]
    params: BroadIndexBacktestParams


class BroadIndexSignalParams(BaseModel):
    label: str | None = None
    holdings: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional current holdings payload (same shape as holdings.json:"
            " {as_of, cash_cny, positions: [{ts_code, shares}]})."
        ),
    )
    initial_cash_if_empty: float = Field(default=1_000_000.0, gt=0)
    sleeve_weights: dict[str, float] | None = None
    cash_buffer: float = Field(default=0.01, ge=0.0, lt=1.0)
    max_weight: float = Field(default=0.4, gt=0.0, le=1.0)
    abs_band_pp: float = Field(default=5.0, ge=0.0)
    rel_band_pct: float = Field(default=25.0, ge=0.0)
    force_rebalance: bool = False


class CreateSignalRequest(BaseModel):
    params: BroadIndexSignalParams = Field(default_factory=BroadIndexSignalParams)


class SuggestParamsRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class SuggestParamsResponse(BaseModel):
    params: BroadIndexBacktestParams


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
