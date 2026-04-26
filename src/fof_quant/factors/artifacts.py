from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from fof_quant.factors.engine import FactorSnapshot


def write_factor_snapshots(
    snapshots: list[FactorSnapshot],
    output_dir: Path,
    rebalance_date: date,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"factor_snapshots_{rebalance_date.isoformat()}.json"
    path.write_text(
        json.dumps(
            [asdict(snapshot) for snapshot in snapshots],
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return path
