from datetime import date

import pytest

from fof_quant.factors.calculators import PriceBar, calculate_price_factors


def test_calculate_price_factors_uses_point_in_time_prices() -> None:
    factors = calculate_price_factors(
        [
            PriceBar("600000.SH", date(2024, 1, 1), 10.0, amount=100.0),
            PriceBar("600000.SH", date(2024, 1, 2), 11.0, amount=200.0),
            PriceBar("600000.SH", date(2024, 1, 3), 99.0, amount=999.0),
        ],
        as_of_date=date(2024, 1, 2),
    )

    by_factor = {factor.factor: factor for factor in factors}

    assert by_factor["momentum"].value == pytest.approx(0.1)
    assert by_factor["liquidity"].value == pytest.approx(150.0)
    assert "volatility" in by_factor
