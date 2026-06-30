from fof_quant.data.broad_index import (
    BROAD_INDEX_SPECS,
    IndexSpec,
    filter_etfs_for_spec,
)

_HS300 = next(s for s in BROAD_INDEX_SPECS if s.label == "沪深300")


def _row(name: str, benchmark: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ts_code": "510300.SH",
        "name": name,
        "benchmark": benchmark,
        "status": "L",
        "invest_type": "被动指数型",
        "list_date": "20120528",
    }
    base.update(overrides)
    return base


def test_benchmark_with_weight_suffix_matches() -> None:
    # Tushare now appends a ×100% weight to fund_basic.benchmark; pure trackers
    # must still match their sleeve spec.
    rows = [_row("华泰柏瑞沪深300ETF", "沪深300指数收益率×100%")]
    matched = filter_etfs_for_spec(rows, _HS300)
    assert [r["_sleeve"] for r in matched] == ["沪深300"]


def test_plain_benchmark_without_suffix_still_matches() -> None:
    rows = [_row("华泰柏瑞沪深300ETF", "沪深300指数收益率")]
    assert len(filter_etfs_for_spec(rows, _HS300)) == 1


def test_composite_and_strategy_benchmarks_are_rejected() -> None:
    rows = [
        # composite (parts each <100%) must not be treated as a 沪深300 tracker
        _row("某沪深300混合ETF", "沪深300指数收益率×80%+中债综合指数收益率×20%"),
        # quality/strategy variant on a different index name
        _row("兴全沪深300质量ETF", "沪深300质量指数收益率×100%"),
        # enhanced funds are excluded by invest_type
        _row("某沪深300增强ETF", "沪深300指数收益率×100%", invest_type="增强指数型"),
    ]
    assert filter_etfs_for_spec(rows, _HS300) == []


def test_non_etf_name_rejected() -> None:
    rows = [_row("某沪深300指数基金", "沪深300指数收益率×100%")]
    assert filter_etfs_for_spec(rows, _HS300) == []


def test_all_specs_match_weight_suffix_form() -> None:
    # every sleeve's canonical benchmark, now carrying the ×100% suffix, resolves.
    canonical = {
        "上证50": "上证50指数收益率×100%",
        "沪深300": "沪深300指数收益率×100%",
        "中证A500": "中证A500指数收益率×100%",
        "中证500": "中证500指数收益率×100%",
        "中证1000": "中证1000指数收益率×100%",
        "创业板指": "创业板指数收益率×100%",
        "科创50": "上证科创板50成份指数收益率×100%",
        "中证红利低波": "中证红利低波动指数收益率×100%",
    }
    for spec in BROAD_INDEX_SPECS:
        rows = [_row(f"测试{spec.label}ETF", canonical[spec.label])]
        assert len(filter_etfs_for_spec(rows, spec)) == 1, spec.label


def test_unrelated_spec_does_not_match() -> None:
    spec = IndexSpec("上证50", "000016.SH", "H00016.CSI", r"^上证50指数(收益率)?$")
    rows = [_row("华泰柏瑞沪深300ETF", "沪深300指数收益率×100%")]
    assert filter_etfs_for_spec(rows, spec) == []
