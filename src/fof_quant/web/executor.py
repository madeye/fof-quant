from __future__ import annotations

import json
import logging
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fof_quant.data.broad_index import ensure_broad_index_cache_fresh
from fof_quant.web.registry import RunRegistry
from fof_quant.web.schemas import BroadIndexBacktestParams, BroadIndexSignalParams

logger = logging.getLogger(__name__)


def execute_broad_index_backtest(
    *,
    registry: RunRegistry,
    run_id: str,
    cache_dir: Path,
    output_dir: Path,
    params: BroadIndexBacktestParams,
) -> None:
    """Run a broad-index backtest in-process and update the registry.

    Imported lazily so the web package's module imports don't pay the cost of
    pulling in pandas / pipeline machinery for every API call.
    """
    registry.update_status(run_id, "running")
    try:
        end_date = _parse_iso_date(params.end_date)
        ensure_broad_index_cache_fresh(cache_dir, end_date=end_date)

        from fof_quant.pipeline_broad_index import run_broad_index_backtest_pipeline

        start_date = _parse_iso_date(params.start_date)
        backtest, manifest_path, report, _narrative = run_broad_index_backtest_pipeline(
            cache_dir=cache_dir,
            output_dir=output_dir,
            start_date=start_date,
            end_date=end_date,
            initial_cash=params.initial_cash,
            sleeve_weights=params.sleeve_weights,
            cash_buffer=params.cash_buffer,
            max_weight=params.max_weight,
            abs_band_pp=params.abs_band_pp,
            rel_band_pct=params.rel_band_pct,
            transaction_cost_bps=params.transaction_cost_bps,
            slippage_bps=params.slippage_bps,
            benchmark_label=params.benchmark_label,
            write_report=True,
            explain_with_llm=False,
            regime_kind=params.regime_kind,
            bull_sleeve_weights=params.bull_sleeve_weights,
            bear_sleeve_weights=params.bear_sleeve_weights,
        )
        as_of = _curve_end_date(backtest)
        registry.update_status(
            run_id,
            "completed",
            manifest_path=str(manifest_path),
            report_html_path=str(report.html_path) if report else None,
            as_of_date=as_of,
        )
    except Exception as exc:  # pragma: no cover - error surface is exercised manually
        logger.exception("broad_index_backtest run %s failed", run_id)
        message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        registry.update_status(run_id, "failed", error=message)


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def execute_broad_index_signal(
    *,
    registry: RunRegistry,
    run_id: str,
    cache_dir: Path,
    output_dir: Path,
    params: BroadIndexSignalParams,
) -> None:
    """Run a broad-index signal in-process and update the registry."""
    registry.update_status(run_id, "running")
    try:
        ensure_broad_index_cache_fresh(cache_dir)

        from fof_quant.pipeline_broad_index import run_broad_index_pipeline

        holdings_path: Path | None = None
        if params.holdings is not None:
            holdings_path = output_dir / "holdings.json"
            holdings_path.write_text(
                json.dumps(params.holdings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        artifacts = run_broad_index_pipeline(
            cache_dir=cache_dir,
            output_dir=output_dir,
            holdings_path=holdings_path,
            initial_cash_if_empty=params.initial_cash_if_empty,
            sleeve_weights=params.sleeve_weights,
            cash_buffer=params.cash_buffer,
            max_weight=params.max_weight,
            abs_band_pp=params.abs_band_pp,
            rel_band_pct=params.rel_band_pct,
            force_rebalance=params.force_rebalance,
            write_report=True,
            explain_with_llm=False,
        )
        registry.update_status(
            run_id,
            "completed",
            manifest_path=str(artifacts.manifest_path),
            report_html_path=(
                str(artifacts.report.html_path) if artifacts.report else None
            ),
            as_of_date=_signal_as_of(artifacts.manifest_path),
        )
    except Exception as exc:  # pragma: no cover - error surface is exercised manually
        logger.exception("broad_index_signal run %s failed", run_id)
        message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        registry.update_status(run_id, "failed", error=message)


def _signal_as_of(manifest_path: Path) -> str | None:
    try:
        payload: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    as_of = payload.get("as_of") if isinstance(payload, dict) else None
    return str(as_of) if as_of else None


def _curve_end_date(backtest: object) -> str | None:
    curve = getattr(backtest, "curve", None)
    if not curve:
        return None
    last = curve[-1]
    end = getattr(last, "trade_date", None)
    if isinstance(end, date):
        return end.isoformat()
    return str(end) if end else None
