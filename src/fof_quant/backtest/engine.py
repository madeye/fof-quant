from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fof_quant.allocation.engine import AllocationPlan
from fof_quant.backtest.metrics import PerformanceMetrics, calculate_metrics


@dataclass(frozen=True)
class PricePoint:
    trade_date: date
    etf_code: str
    close: float


@dataclass(frozen=True)
class PortfolioPoint:
    trade_date: date
    nav: float
    daily_return: float
    drawdown: float


@dataclass(frozen=True)
class BacktestResult:
    curve: list[PortfolioPoint]
    metrics: PerformanceMetrics
    turnover: float


class BacktestEngine:
    def __init__(
        self,
        *,
        initial_cash: float,
        transaction_cost_bps: float,
        slippage_bps: float,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.initial_cash = initial_cash
        self.cost_rate = (transaction_cost_bps + slippage_bps) / 10_000

    def run(self, prices: list[PricePoint], allocation: AllocationPlan) -> BacktestResult:
        holdings = {row.etf_code: row.weight for row in allocation.holdings}
        dates = sorted({price.trade_date for price in prices})
        price_index = {(price.trade_date, price.etf_code): price.close for price in prices}
        if not dates or not holdings:
            empty_curve = [
                PortfolioPoint(trade_date=dates[0], nav=1.0, daily_return=0.0, drawdown=0.0)
            ] if dates else []
            return BacktestResult(
                curve=empty_curve,
                metrics=calculate_metrics(empty_curve),
                turnover=0.0,
            )

        turnover = sum(abs(weight) for weight in holdings.values())
        cost = turnover * self.cost_rate
        curve: list[PortfolioPoint] = []
        previous_nav = 1.0 - cost
        peak_nav = previous_nav
        first_date = dates[0]
        base_prices = {code: price_index[(first_date, code)] for code in holdings}
        for trade_date in dates:
            gross_nav = sum(
                weight * price_index[(trade_date, code)] / base_prices[code]
                for code, weight in holdings.items()
                if (trade_date, code) in price_index
            ) + allocation.cash_weight
            nav = gross_nav - cost
            daily_return = 0.0 if not curve else nav / previous_nav - 1.0
            peak_nav = max(peak_nav, nav)
            drawdown = nav / peak_nav - 1.0
            curve.append(PortfolioPoint(trade_date, nav, daily_return, drawdown))
            previous_nav = nav
        return BacktestResult(curve=curve, metrics=calculate_metrics(curve), turnover=turnover)
