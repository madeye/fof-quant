from __future__ import annotations

from datetime import date
from pathlib import Path

from fof_quant.analysis.sweep import (
    DEFAULT_BANDS_PP,
    QUICK_BANDS_PP,
    QUICK_SCHEMES,
    SCHEMES,
    render_sweep_table,
    run_sweep,
    write_sweep_csv,
)
from fof_quant.data.broad_index import BroadIndexFetchResult, IndexSpec
from fof_quant.data.provider import DataTable


def _make_fetched() -> BroadIndexFetchResult:
    """Tiny synthetic fixture: 2 sleeves × 1 ETF each, 60 days at 0.5% daily."""
    specs = (
        IndexSpec("沪深300", "000300.SH", "H00300.CSI", r"^沪深300指数$"),
        IndexSpec("中证1000", "000852.SH", "H00852.CSI", r"^中证1000指数$"),
    )
    universe = DataTable(
        dataset="etf_basic",
        rows=[
            {
                "ts_code": "510300.SH",
                "name": "沪深300ETF",
                "list_date": "20100101",
                "m_fee": 0.15,
                "c_fee": 0.05,
                "_sleeve": "沪深300",
                "status": "L",
                "invest_type": "被动指数型",
                "benchmark": "沪深300指数",
                "management": "AAA",
            },
            {
                "ts_code": "512100.SH",
                "name": "中证1000ETF",
                "list_date": "20100101",
                "m_fee": 0.15,
                "c_fee": 0.05,
                "_sleeve": "中证1000",
                "status": "L",
                "invest_type": "被动指数型",
                "benchmark": "中证1000指数",
                "management": "BBB",
            },
        ],
    )
    days = [date(2024, 1, d) for d in range(2, 32)] + [date(2024, 2, d) for d in range(1, 30)]
    fund_nav_rows: list[dict[str, object]] = []
    etf_daily_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    for code in ("510300.SH", "512100.SH"):
        nav = 1.0
        for d in days:
            nav *= 1.005
            fund_nav_rows.append(
                {
                    "ts_code": code,
                    "nav_date": d.strftime("%Y%m%d"),
                    "unit_nav": nav,
                    "accum_nav": nav,
                    "adj_nav": nav,
                }
            )
            etf_daily_rows.append(
                {
                    "ts_code": code,
                    "trade_date": d.strftime("%Y%m%d"),
                    "close": nav * 4.0,
                    "amount": 5_000_000.0,
                }
            )
    for spec in specs:
        nav = 1000.0
        for d in days:
            nav *= 1.005
            benchmark_rows.append(
                {
                    "ts_code": spec.total_return_code,
                    "trade_date": d.strftime("%Y%m%d"),
                    "close": nav,
                }
            )
    return BroadIndexFetchResult(
        specs=specs,
        universe=universe,
        fund_nav=DataTable(dataset="fund_nav", rows=fund_nav_rows),
        etf_daily=DataTable(dataset="etf_daily", rows=etf_daily_rows),
        benchmarks=DataTable(dataset="benchmarks", rows=benchmark_rows),
    )


def test_schemes_all_sum_to_one() -> None:
    for name, weights in SCHEMES.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, name


def test_quick_subset_is_subset() -> None:
    assert set(QUICK_SCHEMES) <= set(SCHEMES)
    assert set(QUICK_BANDS_PP) <= set(DEFAULT_BANDS_PP)


def test_run_sweep_shape() -> None:
    fetched = _make_fetched()
    schemes = {
        "balanced_2": {"沪深300": 0.5, "中证1000": 0.5},
        "core_only": {"沪深300": 1.0},
    }
    bands = (3.0, 7.0)
    rows, benchmark, backtests = run_sweep(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 2, 29),
        initial_cash=1_000_000.0,
        schemes=schemes,
        bands_pp=bands,
        cash_buffer=0.0,
        max_weight=0.6,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    assert len(rows) == len(schemes) * len(bands)
    assert len(backtests) == len(rows)
    # Same input data → benchmark metrics should be identical regardless of scheme/band
    assert benchmark is not None
    pairs = {(r.scheme, r.band_pp) for r in rows}
    assert pairs == {(name, b) for name in schemes for b in bands}


def test_render_sweep_table_handles_empty() -> None:
    text = render_sweep_table([])
    assert "no sweep results" in text


def test_write_sweep_csv_round_trip(tmp_path: Path) -> None:
    fetched = _make_fetched()
    rows, _, _ = run_sweep(
        fetched,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 31),
        initial_cash=1_000_000.0,
        schemes={"core_only": {"沪深300": 1.0}},
        bands_pp=(5.0,),
        cash_buffer=0.0,
        max_weight=1.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    out_path = write_sweep_csv(rows, tmp_path, end_date=date(2024, 1, 31))
    assert out_path.exists()
    body = out_path.read_text(encoding="utf-8")
    assert "scheme,band_pp,final_nav" in body
    assert "core_only,5.0" in body
