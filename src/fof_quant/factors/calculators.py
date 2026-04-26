from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

from fof_quant.factors.exposure import StockFactor


@dataclass(frozen=True)
class PriceBar:
    stock_code: str
    trade_date: date
    close: float
    amount: float = 0.0


def calculate_price_factors(price_bars: list[PriceBar], *, as_of_date: date) -> list[StockFactor]:
    by_stock: dict[str, list[PriceBar]] = {}
    for bar in price_bars:
        if bar.trade_date <= as_of_date:
            by_stock.setdefault(bar.stock_code, []).append(bar)
    factors: list[StockFactor] = []
    for stock_code, bars in by_stock.items():
        ordered = sorted(bars, key=lambda item: item.trade_date)
        if len(ordered) < 2:
            continue
        returns = [
            ordered[index].close / ordered[index - 1].close - 1.0
            for index in range(1, len(ordered))
            if ordered[index - 1].close > 0
        ]
        if not returns:
            continue
        momentum = ordered[-1].close / ordered[0].close - 1.0
        volatility = _sample_volatility(returns) * sqrt(252)
        liquidity = sum(bar.amount for bar in ordered) / len(ordered)
        factors.extend(
            [
                StockFactor(stock_code, "momentum", momentum, as_of_date),
                StockFactor(stock_code, "volatility", volatility, as_of_date),
                StockFactor(stock_code, "liquidity", liquidity, as_of_date),
            ]
        )
    return factors


def _sample_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance)
