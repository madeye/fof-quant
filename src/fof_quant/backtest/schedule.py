from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Literal


def rebalance_dates(
    trading_days: list[date],
    frequency: Literal["weekly", "monthly", "quarterly"],
) -> list[date]:
    if not trading_days:
        return []
    ordered = sorted(trading_days)
    if frequency == "weekly":
        return _last_by_key(ordered, lambda item: item.isocalendar()[:2])
    if frequency == "monthly":
        return _last_by_key(ordered, lambda item: (item.year, item.month))
    return _last_by_key(ordered, lambda item: (item.year, (item.month - 1) // 3))


def _last_by_key(trading_days: list[date], key: Callable[[date], object]) -> list[date]:
    output: list[date] = []
    previous_key: object | None = None
    for index, trade_date in enumerate(trading_days):
        current_key = key(trade_date)
        next_key = key(trading_days[index + 1]) if index + 1 < len(trading_days) else None
        if (current_key != previous_key and index == len(trading_days) - 1) or (
            current_key != next_key
        ):
            output.append(trade_date)
        previous_key = current_key
    return output
