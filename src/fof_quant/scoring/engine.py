from __future__ import annotations

from dataclasses import dataclass

from fof_quant.factors.engine import FactorSnapshot


@dataclass(frozen=True)
class ScoreRow:
    etf_code: str
    score: float
    normalized_factors: dict[str, float]
    contributions: dict[str, float]
    eligible: bool = True
    reason: str = ""


class ScoringEngine:
    def __init__(self, factor_weights: dict[str, float]) -> None:
        if not factor_weights:
            raise ValueError("factor_weights must not be empty")
        self.factor_weights = factor_weights

    def score(self, snapshots: list[FactorSnapshot]) -> list[ScoreRow]:
        normalized = _normalize_snapshots(snapshots, sorted(self.factor_weights))
        rows: list[ScoreRow] = []
        for snapshot in snapshots:
            values = normalized.get(snapshot.etf_code, {})
            contributions = {
                factor: values.get(factor, 0.0) * weight
                for factor, weight in self.factor_weights.items()
            }
            rows.append(
                ScoreRow(
                    etf_code=snapshot.etf_code,
                    score=sum(contributions.values()),
                    normalized_factors=values,
                    contributions=contributions,
                    eligible=bool(snapshot.exposures),
                    reason="" if snapshot.exposures else "missing factor exposures",
                )
            )
        return sorted(rows, key=lambda row: (-row.eligible, -row.score, row.etf_code))


def _normalize_snapshots(
    snapshots: list[FactorSnapshot],
    factors: list[str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {snapshot.etf_code: {} for snapshot in snapshots}
    for factor in factors:
        values = [
            snapshot.exposures[factor] for snapshot in snapshots if factor in snapshot.exposures
        ]
        if not values:
            continue
        low, high = min(values), max(values)
        for snapshot in snapshots:
            if factor not in snapshot.exposures:
                continue
            value = snapshot.exposures[factor]
            result[snapshot.etf_code][factor] = 0.0 if high == low else (value - low) / (high - low)
    return result
