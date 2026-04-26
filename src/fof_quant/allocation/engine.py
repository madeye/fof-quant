from __future__ import annotations

from dataclasses import dataclass

from fof_quant.scoring.engine import ScoreRow


@dataclass(frozen=True)
class AllocationRow:
    etf_code: str
    weight: float
    score: float
    reason: str


@dataclass(frozen=True)
class AllocationPlan:
    holdings: list[AllocationRow]
    cash_weight: float
    constraint_checks: dict[str, bool]


class AllocationEngine:
    def __init__(
        self,
        *,
        min_holdings: int,
        max_weight: float,
        cash_buffer: float,
    ) -> None:
        if min_holdings < 1:
            raise ValueError("min_holdings must be at least 1")
        if not 0 < max_weight <= 1:
            raise ValueError("max_weight must be in (0, 1]")
        if not 0 <= cash_buffer < 1:
            raise ValueError("cash_buffer must be in [0, 1)")
        self.min_holdings = min_holdings
        self.max_weight = max_weight
        self.cash_buffer = cash_buffer

    def allocate(self, scores: list[ScoreRow]) -> AllocationPlan:
        eligible = [row for row in scores if row.eligible]
        selected = eligible[: self.min_holdings]
        investable = 1.0 - self.cash_buffer
        if not selected:
            return AllocationPlan(
                holdings=[],
                cash_weight=1.0,
                constraint_checks={"min_holdings": False, "max_weight": True, "cash_buffer": True},
            )
        raw_weight = min(self.max_weight, investable / len(selected))
        holdings = [
            AllocationRow(
                etf_code=row.etf_code,
                weight=raw_weight,
                score=row.score,
                reason="selected by rank",
            )
            for row in selected
        ]
        allocated = sum(row.weight for row in holdings)
        cash_weight = 1.0 - allocated
        return AllocationPlan(
            holdings=holdings,
            cash_weight=cash_weight,
            constraint_checks={
                "min_holdings": len(holdings) >= self.min_holdings,
                "max_weight": all(row.weight <= self.max_weight for row in holdings),
                "cash_buffer": cash_weight >= self.cash_buffer,
            },
        )
