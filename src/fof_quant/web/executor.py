from __future__ import annotations

import logging
import traceback
from datetime import date, datetime
from pathlib import Path

from fof_quant.web.registry import RunRegistry
from fof_quant.web.schemas import BroadIndexBacktestParams

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
        from fof_quant.pipeline_broad_index import run_broad_index_backtest_pipeline

        start_date = _parse_iso_date(params.start_date)
        end_date = _parse_iso_date(params.end_date)
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


def _curve_end_date(backtest: object) -> str | None:
    curve = getattr(backtest, "curve", None)
    if not curve:
        return None
    last = curve[-1]
    end = getattr(last, "trade_date", None)
    if isinstance(end, date):
        return end.isoformat()
    return str(end) if end else None
