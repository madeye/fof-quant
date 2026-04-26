from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fof_quant.backtest.engine import BacktestResult


def write_backtest_result(result: BacktestResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "backtest.json"
    payload = {
        "curve": [asdict(point) for point in result.curve],
        "metrics": asdict(result.metrics),
        "turnover": result.turnover,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path
