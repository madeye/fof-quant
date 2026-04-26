from datetime import date

import pytest

from fof_quant.factors.engine import FactorEngine, FactorInput
from fof_quant.factors.exposure import ExposureResolver, Holding, StockFactor


def test_factor_engine_aggregates_stock_through_exposures() -> None:
    resolver = ExposureResolver(
        fund_holdings=[
            Holding("510300.SH", "600000.SH", 70.0, date(2024, 1, 1), "fund_holdings"),
            Holding("510300.SH", "000001.SZ", 30.0, date(2024, 1, 1), "fund_holdings"),
        ],
        index_holdings=[],
    )
    engine = FactorEngine(resolver)

    snapshots = engine.build(
        FactorInput(
            etf_codes=["510300.SH"],
            rebalance_date=date(2024, 1, 31),
            stock_factors=[
                StockFactor("600000.SH", "momentum", 1.0, date(2024, 1, 30)),
                StockFactor("000001.SZ", "momentum", 2.0, date(2024, 1, 30)),
            ],
        )
    )

    assert snapshots[0].exposures["momentum"] == pytest.approx(1.3)
    assert snapshots[0].coverage["momentum"] == 1.0
    assert snapshots[0].source == "fund_holdings"


def test_factor_engine_falls_back_to_index_holdings() -> None:
    resolver = ExposureResolver(
        fund_holdings=[],
        index_holdings=[
            Holding("510300.SH", "600000.SH", 1.0, date(2024, 1, 1), "index_weight"),
        ],
    )
    engine = FactorEngine(resolver)

    snapshot = engine.build(
        FactorInput(
            etf_codes=["510300.SH"],
            rebalance_date=date(2024, 1, 31),
            stock_factors=[StockFactor("600000.SH", "value", 3.0, date(2024, 1, 30))],
        )
    )[0]

    assert snapshot.exposures == {"value": 3.0}
    assert snapshot.source == "index_weight"


def test_factor_engine_uses_point_in_time_inputs() -> None:
    resolver = ExposureResolver(
        fund_holdings=[
            Holding("510300.SH", "600000.SH", 1.0, date(2024, 2, 1), "fund_holdings"),
        ],
        index_holdings=[],
    )
    engine = FactorEngine(resolver)

    snapshot = engine.build(
        FactorInput(
            etf_codes=["510300.SH"],
            rebalance_date=date(2024, 1, 31),
            stock_factors=[
                StockFactor("600000.SH", "momentum", 1.0, date(2024, 1, 30)),
                StockFactor("600000.SH", "momentum", 99.0, date(2024, 2, 1)),
            ],
        )
    )[0]

    assert snapshot.holding_count == 0
    assert snapshot.exposures == {}
