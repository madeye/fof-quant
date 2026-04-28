from __future__ import annotations

from datetime import date, timedelta

import pytest

from fof_quant.portfolio.regime import Sma200HysteresisRegime


def _series(values: list[float], start: date = date(2024, 1, 2)) -> dict[date, float]:
    return {start + timedelta(days=i): v for i, v in enumerate(values)}


def test_warmup_period_defaults_to_bear() -> None:
    closes = _series([100.0] * 10)
    regime = Sma200HysteresisRegime(closes, sma_window=5)
    days = sorted(closes)
    # First few days have no SMA → must be bear
    assert regime.signal_for_date(days[0]) == "bear"
    assert regime.signal_for_date(days[3]) == "bear"


def test_enters_bull_when_close_clears_up_threshold() -> None:
    # 10 flat days at 100 (SMA stabilizes near 100), then 3 days at 110.
    # By the third 110 day, prior-day close = 110 and prior-day SMA still
    # averages mostly 100s + a couple 110s, so ratio > 1.05 → bull.
    closes = _series([100.0] * 10 + [110.0] * 3)
    regime = Sma200HysteresisRegime(closes, sma_window=5, up_thresh=0.05, down_thresh=0.03)
    days = sorted(closes)
    assert regime.signal_for_date(days[-1]) == "bull"


def test_exits_bull_when_close_breaks_down_threshold() -> None:
    # Start: 5 days at 100 (warmup). Then 10 days at 120 (bull).
    # Then 5 days at 95 to break ratio < 0.97 against the rising SMA.
    closes = _series([100.0] * 5 + [120.0] * 10 + [85.0] * 6)
    regime = Sma200HysteresisRegime(closes, sma_window=5, up_thresh=0.05, down_thresh=0.03)
    days = sorted(closes)
    # By the last day, prior close is 85, prior SMA mixes 120s/85s but should
    # be elevated enough that 85/SMA < 0.97.
    assert regime.signal_for_date(days[-1]) == "bear"


def test_hysteresis_avoids_chop_whipsaw() -> None:
    # Close oscillates within ±2% of SMA — should NEVER flip with 5%/3% bands.
    base = 100.0
    values = [base * (1.0 + 0.02 * (1 if i % 2 else -1)) for i in range(40)]
    closes = _series(values)
    regime = Sma200HysteresisRegime(closes, sma_window=10, up_thresh=0.05, down_thresh=0.03)
    states = [regime.signal_for_date(d) for d in sorted(closes)]
    # Stayed in initial bear the whole time (never crossed 5% above SMA)
    assert all(s == "bear" for s in states)


def test_no_lookahead_uses_prior_day() -> None:
    """signal_for_date(d) must depend on prior trading day's close, not d itself."""
    # Day N close jumps to 120 from a 100 baseline. Day N's signal must NOT
    # already be bull — it should still reflect the day-N-1 SMA cross state.
    closes = _series([100.0] * 10 + [120.0])
    regime = Sma200HysteresisRegime(closes, sma_window=5, up_thresh=0.05, down_thresh=0.03)
    days = sorted(closes)
    # Day where the jump happens: signal should still be bear because prior
    # close (=100) and prior SMA (=100) gives ratio 1.0, not > 1.05.
    assert regime.signal_for_date(days[-1]) == "bear"


def test_unknown_date_returns_bear() -> None:
    closes = _series([100.0] * 10)
    regime = Sma200HysteresisRegime(closes, sma_window=5)
    far_future = date(2099, 1, 1)
    assert regime.signal_for_date(far_future) == "bear"


def test_callable_alias_matches_method() -> None:
    closes = _series([100.0] * 10)
    regime = Sma200HysteresisRegime(closes, sma_window=5)
    d = sorted(closes)[5]
    assert regime(d) == regime.signal_for_date(d)


def test_invalid_thresholds_raise() -> None:
    with pytest.raises(ValueError):
        Sma200HysteresisRegime({date(2024, 1, 1): 100.0}, sma_window=1)
    with pytest.raises(ValueError):
        Sma200HysteresisRegime(
            {date(2024, 1, 1): 100.0}, sma_window=5, up_thresh=-0.01
        )
    with pytest.raises(ValueError):
        Sma200HysteresisRegime(
            {date(2024, 1, 1): 100.0}, sma_window=5, down_thresh=-0.01
        )


def test_precompute_is_order_independent() -> None:
    """Calling signal_for_date in random order returns the same answers as ascending."""
    import random

    closes = _series(
        [100.0 + 0.5 * i for i in range(50)]  # rising trend
        + [150.0 - 0.6 * i for i in range(40)]  # falling trend
    )
    regime = Sma200HysteresisRegime(closes, sma_window=10, up_thresh=0.05, down_thresh=0.03)
    days = sorted(closes)
    in_order = [regime.signal_for_date(d) for d in days]

    rng = random.Random(42)
    shuffled = days.copy()
    rng.shuffle(shuffled)
    out_of_order_map = {d: regime.signal_for_date(d) for d in shuffled}
    out_of_order = [out_of_order_map[d] for d in days]

    assert in_order == out_of_order
