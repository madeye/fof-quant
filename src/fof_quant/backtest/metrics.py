from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Protocol


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annualized_return: float
    volatility: float
    sharpe: float
    max_drawdown: float
    calmar: float
    win_rate: float
    tracking_error: float


class PortfolioPointLike(Protocol):
    @property
    def nav(self) -> float: ...

    @property
    def daily_return(self) -> float: ...

    @property
    def drawdown(self) -> float: ...


def calculate_metrics(
    curve: Sequence[PortfolioPointLike],
    benchmark_returns: Sequence[float] | None = None,
) -> PerformanceMetrics:
    if not curve:
        return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    navs = [point.nav for point in curve]
    returns = [point.daily_return for point in curve[1:]]
    drawdowns = [point.drawdown for point in curve]
    total_return = navs[-1] / navs[0] - 1.0 if navs[0] else 0.0
    periods = max(len(navs) - 1, 1)
    annualized_return = (1.0 + total_return) ** (252 / periods) - 1.0
    volatility = _sample_volatility(returns) * sqrt(252)
    sharpe = annualized_return / volatility if volatility else 0.0
    max_drawdown = min(drawdowns)
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
    win_rate = sum(1 for value in returns if value > 0) / len(returns) if returns else 0.0
    tracking_error = _tracking_error(returns, benchmark_returns)
    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        volatility=volatility,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        calmar=calmar,
        win_rate=win_rate,
        tracking_error=tracking_error,
    )


def _sample_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance)


def _tracking_error(returns: list[float], benchmark_returns: Sequence[float] | None) -> float:
    if benchmark_returns is None:
        return 0.0
    paired = list(zip(returns, benchmark_returns, strict=False))
    if len(paired) < 2:
        return 0.0
    active = [portfolio - benchmark for portfolio, benchmark in paired]
    return _sample_volatility(active) * sqrt(252)
