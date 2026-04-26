from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fof_quant.factors.exposure import ExposureResolver, Holding, StockFactor


@dataclass(frozen=True)
class FactorInput:
    etf_codes: list[str]
    rebalance_date: date
    stock_factors: list[StockFactor]


@dataclass(frozen=True)
class FactorSnapshot:
    etf_code: str
    rebalance_date: date
    exposures: dict[str, float]
    coverage: dict[str, float]
    holding_count: int
    source: str


class FactorEngine:
    def __init__(self, resolver: ExposureResolver) -> None:
        self.resolver = resolver

    def build(self, factor_input: FactorInput) -> list[FactorSnapshot]:
        factor_index = _latest_factor_index(
            factor_input.stock_factors,
            factor_input.rebalance_date,
        )
        return [
            self._snapshot_for_etf(etf_code, factor_input.rebalance_date, factor_index)
            for etf_code in factor_input.etf_codes
        ]

    def _snapshot_for_etf(
        self,
        etf_code: str,
        rebalance_date: date,
        factor_index: dict[tuple[str, str], float],
    ) -> FactorSnapshot:
        holdings = self.resolver.resolve(etf_code, rebalance_date)
        factor_names = sorted({factor for _, factor in factor_index})
        exposures: dict[str, float] = {}
        coverage: dict[str, float] = {}
        for factor in factor_names:
            weighted_sum = 0.0
            covered_weight = 0.0
            for holding in holdings:
                value = factor_index.get((holding.stock_code, factor))
                if value is None:
                    continue
                weighted_sum += holding.weight * value
                covered_weight += holding.weight
            if covered_weight > 0:
                exposures[factor] = weighted_sum / covered_weight
                coverage[factor] = covered_weight
        return FactorSnapshot(
            etf_code=etf_code,
            rebalance_date=rebalance_date,
            exposures=exposures,
            coverage=coverage,
            holding_count=len(holdings),
            source=_snapshot_source(holdings),
        )


def _latest_factor_index(
    stock_factors: list[StockFactor],
    rebalance_date: date,
) -> dict[tuple[str, str], float]:
    latest: dict[tuple[str, str], StockFactor] = {}
    for item in stock_factors:
        if item.as_of_date > rebalance_date:
            continue
        key = (item.stock_code, item.factor)
        current = latest.get(key)
        if current is None or item.as_of_date > current.as_of_date:
            latest[key] = item
    return {key: item.value for key, item in latest.items()}


def _snapshot_source(holdings: list[Holding]) -> str:
    if not holdings:
        return "none"
    sources = sorted({holding.source for holding in holdings})
    return "+".join(sources)
