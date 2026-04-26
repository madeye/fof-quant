from datetime import date

from fof_quant.backtest.schedule import rebalance_dates


def test_rebalance_dates_select_month_end_trading_days() -> None:
    days = [
        date(2024, 1, 29),
        date(2024, 1, 31),
        date(2024, 2, 1),
        date(2024, 2, 29),
    ]

    assert rebalance_dates(days, "monthly") == [date(2024, 1, 31), date(2024, 2, 29)]
