"""Bull/bear regime providers for sleeve-switch overlays.

A `RegimeProvider` returns "bull" or "bear" for a given trade date and is
used by `backtest_broad_index.run_broad_index_backtest` to pick between
two sleeve-weight maps at each rebalance. The interface is intentionally
small — a callable `(date) -> "bull"|"bear"` — so additional regime
strategies (vol target, multi-factor, etc.) can be added without touching
the engine.

`Sma200HysteresisRegime` is the v1 implementation. It uses a moving
average of the configured benchmark close, with hysteresis on entry and
exit thresholds to avoid whipsaws. Walk-forward (2018–2026 split into
two 4-year windows) shows SMA200 + 5%/3% bands lift Sharpe by +0.21 OOS
on the equal_5/defensive switch vs the best static config.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import Literal, Protocol

Regime = Literal["bull", "bear"]


class RegimeProvider(Protocol):
    """Returns the bull/bear regime label for a given trade date.

    Implementations may be path-dependent (e.g. hysteresis) but must be
    deterministic given the same input data. Calls must be safe to
    interleave across dates (precompute or use a state-free signal).
    """

    def signal_for_date(self, d: date) -> Regime: ...


class Sma200HysteresisRegime:
    """Bull/bear regime from benchmark close vs its SMA, with hysteresis.

    Precomputes the regime for every date in the supplied close series so
    `signal_for_date` is O(1) and safe to call out of order. The regime
    state is path-dependent; pre-computation walks dates in ascending
    order and applies the entry/exit thresholds:

      - Enter bull when close / SMA > 1 + up_thresh
      - Exit bull when close / SMA < 1 - down_thresh
      - Default to bear during SMA warmup (cold start)

    The signal for date `d` uses the prior trading day's close and SMA so
    no look-ahead bias leaks into rebalance decisions.
    """

    def __init__(
        self,
        bench_close_by_date: Mapping[date, float],
        *,
        sma_window: int = 200,
        up_thresh: float = 0.05,
        down_thresh: float = 0.03,
    ) -> None:
        if sma_window < 2:
            raise ValueError(f"sma_window must be >= 2, got {sma_window}")
        if up_thresh < 0 or down_thresh < 0:
            raise ValueError("hysteresis thresholds must be non-negative")
        self.sma_window = sma_window
        self.up_thresh = up_thresh
        self.down_thresh = down_thresh
        self._regime_by_date = self._precompute(bench_close_by_date)

    def signal_for_date(self, d: date) -> Regime:
        return self._regime_by_date.get(d, "bear")

    # Allow use as a plain callable: regime(d) == regime.signal_for_date(d)
    def __call__(self, d: date) -> Regime:
        return self.signal_for_date(d)

    def _precompute(self, bench_close_by_date: Mapping[date, float]) -> dict[date, Regime]:
        days = sorted(bench_close_by_date)
        closes = [float(bench_close_by_date[d]) for d in days]
        smas = _rolling_sma(closes, self.sma_window)

        out: dict[date, Regime] = {}
        bull = False
        for i, d in enumerate(days):
            if i == 0:
                out[d] = "bear"
                continue
            prev_close = closes[i - 1]
            prev_sma = smas[i - 1]
            if math.isnan(prev_sma) or prev_sma <= 0:
                out[d] = "bear"
                continue
            ratio = prev_close / prev_sma
            if not bull and ratio > 1.0 + self.up_thresh:
                bull = True
            elif bull and ratio < 1.0 - self.down_thresh:
                bull = False
            out[d] = "bull" if bull else "bear"
        return out


def _rolling_sma(values: list[float], window: int) -> list[float]:
    n = len(values)
    out: list[float] = [float("nan")] * n
    if n < window:
        return out
    s = sum(values[:window])
    out[window - 1] = s / window
    for i in range(window, n):
        s += values[i] - values[i - window]
        out[i] = s / window
    return out


__all__ = ["Regime", "RegimeProvider", "Sma200HysteresisRegime"]
