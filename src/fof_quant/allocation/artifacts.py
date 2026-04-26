from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fof_quant.allocation.engine import AllocationPlan
from fof_quant.scoring.engine import ScoreRow


def write_scores(scores: list[ScoreRow], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "scores.json"
    path.write_text(
        json.dumps([asdict(row) for row in scores], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_allocation(plan: AllocationPlan, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "allocation.json"
    path.write_text(
        json.dumps(asdict(plan), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
