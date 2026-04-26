from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FundCandidate:
    ts_code: str
    name: str
    fund_type: str
    list_date: date
    status: str
    avg_daily_amount: float
    data_coverage_days: int


@dataclass(frozen=True)
class EligibilityResult:
    candidate: FundCandidate
    eligible: bool
    reasons: tuple[str, ...]


class UniverseFilter:
    def __init__(
        self,
        *,
        allowed_fund_types: set[str],
        min_listing_days: int,
        min_avg_daily_amount: float,
        min_data_coverage_days: int,
        include: set[str],
        exclude: set[str],
        as_of_date: date,
    ) -> None:
        self.allowed_fund_types = allowed_fund_types
        self.min_listing_days = min_listing_days
        self.min_avg_daily_amount = min_avg_daily_amount
        self.min_data_coverage_days = min_data_coverage_days
        self.include = include
        self.exclude = exclude
        self.as_of_date = as_of_date

    def evaluate(self, candidates: list[FundCandidate]) -> list[EligibilityResult]:
        return [self._evaluate_one(candidate) for candidate in candidates]

    def eligible_codes(self, candidates: list[FundCandidate]) -> list[str]:
        return [
            result.candidate.ts_code
            for result in self.evaluate(candidates)
            if result.eligible
        ]

    def _evaluate_one(self, candidate: FundCandidate) -> EligibilityResult:
        reasons: list[str] = []
        if candidate.ts_code in self.exclude:
            reasons.append("manual exclude")
        if candidate.status.lower() not in {"listed", "l"}:
            reasons.append("not listed")
        if candidate.fund_type not in self.allowed_fund_types:
            reasons.append("fund type not allowed")
        if (self.as_of_date - candidate.list_date).days < self.min_listing_days:
            reasons.append("insufficient listing age")
        if candidate.avg_daily_amount < self.min_avg_daily_amount:
            reasons.append("insufficient liquidity")
        if candidate.data_coverage_days < self.min_data_coverage_days:
            reasons.append("insufficient data coverage")
        if candidate.ts_code in self.include:
            reasons = [reason for reason in reasons if reason != "fund type not allowed"]
        return EligibilityResult(candidate, eligible=not reasons, reasons=tuple(reasons))
