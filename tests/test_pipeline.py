import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from fof_quant.config import load_config
from fof_quant.data.cache import CacheMetadata, CacheStore
from fof_quant.data.provider import DataRequest, DataTable
from fof_quant.pipeline import run_offline_pipeline


def test_offline_pipeline_writes_manifest(tmp_path: Path) -> None:
    config_text = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "reports"
    config_path.write_text(
        config_text.replace("output_dir: reports", f"output_dir: {output_dir}"),
        encoding="utf-8",
    )

    artifacts = run_offline_pipeline(load_config(config_path))
    manifest = Path(artifacts["manifest"])

    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert "html_report" in payload["artifacts"]
    assert Path(payload["artifacts"]["html_report"]).exists()


def test_offline_pipeline_uses_cached_holdings_and_prices(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = CacheStore(cache_dir)
    _seed_cache(cache)
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "reports"
    config_path.write_text(
        yaml.safe_dump(_minimal_config(cache_dir, output_dir), sort_keys=False),
        encoding="utf-8",
    )

    artifacts = run_offline_pipeline(load_config(config_path))

    allocation = json.loads(Path(artifacts["allocation"]).read_text(encoding="utf-8"))
    held_codes = {row["etf_code"] for row in allocation["holdings"]}
    assert held_codes <= {"510300.SH", "510500.SH"}
    backtest = json.loads(Path(artifacts["backtest"]).read_text(encoding="utf-8"))
    assert len(backtest["curve"]) > 1


def _minimal_config(cache_dir: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "project": {"name": "pipeline-test", "timezone": "Asia/Shanghai"},
        "data": {
            "provider": "tushare",
            "cache_dir": str(cache_dir),
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
        },
        "universe": {
            "fund_types": ["broad_index_etf"],
            "min_listing_days": 30,
            "min_avg_daily_amount": 1.0,
            "include": [],
            "exclude": [],
        },
        "strategy": {
            "rebalance_frequency": "monthly",
            "benchmark": "000300.SH",
            "cash_buffer": 0.01,
            "max_weight": 0.6,
            "min_holdings": 1,
            "turnover_limit": 1.0,
        },
        "factors": {
            "weights": {"momentum": 1.0, "volatility": -0.5, "liquidity": 0.5},
        },
        "backtest": {
            "initial_cash": 1_000_000,
            "transaction_cost_bps": 2.0,
            "slippage_bps": 1.0,
        },
        "reports": {
            "output_dir": str(output_dir),
            "formats": ["excel", "html"],
            "llm_explanations": False,
        },
    }


def _seed_cache(cache: CacheStore) -> None:
    _write(
        cache,
        "etf_basic",
        [
            {
                "ts_code": "510300.SH",
                "name": "华泰柏瑞沪深300ETF",
                "list_date": "20120504",
                "status": "L",
                "benchmark": "沪深300指数收益率",
            },
            {
                "ts_code": "510500.SH",
                "name": "南方中证500ETF",
                "list_date": "20130328",
                "status": "L",
                "benchmark": "中证500指数收益率",
            },
        ],
    )
    etf_daily_rows: list[dict[str, Any]] = []
    for trade_date, close_300, close_500 in [
        ("20240102", 4.00, 6.00),
        ("20240103", 4.05, 6.10),
        ("20240104", 4.10, 6.05),
        ("20240105", 4.15, 6.20),
    ]:
        etf_daily_rows.append(
            {
                "ts_code": "510300.SH",
                "trade_date": trade_date,
                "close": close_300,
                "amount": 1_000_000.0,
            }
        )
        etf_daily_rows.append(
            {
                "ts_code": "510500.SH",
                "trade_date": trade_date,
                "close": close_500,
                "amount": 800_000.0,
            }
        )
    _write(cache, "etf_daily", etf_daily_rows)
    _write(
        cache,
        "fund_portfolio",
        [
            {"ts_code": "510300.SH", "symbol": "600519.SH", "end_date": "20231231", "mkv": 600.0},
            {"ts_code": "510300.SH", "symbol": "601318.SH", "end_date": "20231231", "mkv": 400.0},
            {"ts_code": "510500.SH", "symbol": "002594.SZ", "end_date": "20231231", "mkv": 500.0},
            {"ts_code": "510500.SH", "symbol": "300750.SZ", "end_date": "20231231", "mkv": 500.0},
        ],
    )
    stock_daily_rows: list[dict[str, Any]] = []
    base_prices = {
        "600519.SH": 1700.0,
        "601318.SH": 45.0,
        "002594.SZ": 220.0,
        "300750.SZ": 180.0,
    }
    for stock, base in base_prices.items():
        for offset, trade_date in enumerate(("20240102", "20240103", "20240104", "20240105")):
            stock_daily_rows.append(
                {
                    "ts_code": stock,
                    "trade_date": trade_date,
                    "close": base * (1 + 0.005 * offset),
                    "amount": 1_000_000.0,
                }
            )
    _write(cache, "stock_daily", stock_daily_rows)


def _write(cache: CacheStore, dataset: str, rows: list[dict[str, Any]]) -> None:
    table = DataTable(dataset=dataset, rows=rows)
    metadata = CacheMetadata(
        dataset=dataset,
        provider="tushare",
        request=DataRequest(
            dataset=dataset,
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 5),
            symbols=[],
        ),
        row_count=len(rows),
    )
    cache.write_table(table, metadata)
