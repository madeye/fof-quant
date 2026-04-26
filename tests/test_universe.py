from datetime import date

from fof_quant.universe.eligibility import FundCandidate, UniverseFilter


def test_universe_filter_records_exclusion_reasons() -> None:
    filter_ = UniverseFilter(
        allowed_fund_types={"broad_index_etf"},
        min_listing_days=252,
        min_avg_daily_amount=50_000_000,
        min_data_coverage_days=252,
        include=set(),
        exclude={"510500.SH"},
        as_of_date=date(2024, 1, 31),
    )
    candidates = [
        FundCandidate(
            ts_code="510300.SH",
            name="沪深300ETF",
            fund_type="broad_index_etf",
            list_date=date(2020, 1, 1),
            status="listed",
            avg_daily_amount=100_000_000,
            data_coverage_days=500,
        ),
        FundCandidate(
            ts_code="510500.SH",
            name="中证500ETF",
            fund_type="broad_index_etf",
            list_date=date(2020, 1, 1),
            status="listed",
            avg_daily_amount=100_000_000,
            data_coverage_days=500,
        ),
    ]

    results = filter_.evaluate(candidates)

    assert results[0].eligible is True
    assert results[1].eligible is False
    assert results[1].reasons == ("manual exclude",)


def test_manual_include_can_override_type_only() -> None:
    filter_ = UniverseFilter(
        allowed_fund_types={"broad_index_etf"},
        min_listing_days=252,
        min_avg_daily_amount=50_000_000,
        min_data_coverage_days=252,
        include={"159915.SZ"},
        exclude=set(),
        as_of_date=date(2024, 1, 31),
    )
    candidate = FundCandidate(
        ts_code="159915.SZ",
        name="创业板ETF",
        fund_type="sector_etf",
        list_date=date(2020, 1, 1),
        status="listed",
        avg_daily_amount=100_000_000,
        data_coverage_days=500,
    )

    assert filter_.evaluate([candidate])[0].eligible is True
