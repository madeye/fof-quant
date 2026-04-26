from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Holding:
    etf_code: str
    stock_code: str
    weight: float
    as_of_date: date
    source: str


@dataclass(frozen=True)
class StockFactor:
    stock_code: str
    factor: str
    value: float
    as_of_date: date


class ExposureResolver:
    def __init__(self, fund_holdings: list[Holding], index_holdings: list[Holding]) -> None:
        self.fund_holdings = fund_holdings
        self.index_holdings = index_holdings

    def resolve(self, etf_code: str, rebalance_date: date) -> list[Holding]:
        fund = self._available(self.fund_holdings, etf_code, rebalance_date)
        if fund:
            return normalize_weights(fund)
        index = self._available(self.index_holdings, etf_code, rebalance_date)
        return normalize_weights(index)

    @staticmethod
    def _available(holdings: list[Holding], etf_code: str, rebalance_date: date) -> list[Holding]:
        eligible = [
            holding
            for holding in holdings
            if holding.etf_code == etf_code and holding.as_of_date <= rebalance_date
        ]
        if not eligible:
            return []
        latest_date = max(holding.as_of_date for holding in eligible)
        return [holding for holding in eligible if holding.as_of_date == latest_date]


def normalize_weights(holdings: list[Holding]) -> list[Holding]:
    total = sum(max(holding.weight, 0.0) for holding in holdings)
    if total <= 0:
        return []
    return [
        Holding(
            etf_code=holding.etf_code,
            stock_code=holding.stock_code,
            weight=max(holding.weight, 0.0) / total,
            as_of_date=holding.as_of_date,
            source=holding.source,
        )
        for holding in holdings
    ]
