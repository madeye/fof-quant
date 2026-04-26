from pathlib import Path

import pytest
from pydantic import ValidationError

from fof_quant.config import AppConfig, load_config


def test_example_config_loads() -> None:
    config = load_config(Path("configs/example.yaml"))

    assert config.project.name == "fof-quant-example"
    assert config.data.provider == "tushare"
    assert config.strategy.rebalance_frequency == "monthly"
    assert config.reports.llm_explanations is False


def test_factor_weights_are_required() -> None:
    raw = {
        "project": {"name": "test"},
        "data": {"cache_dir": "cache", "start_date": "2020-01-01"},
        "universe": {},
        "strategy": {"benchmark": "000300.SH"},
        "factors": {"weights": {}},
        "backtest": {},
        "reports": {"output_dir": "reports"},
    }

    with pytest.raises(ValidationError, match="factor weights must not be empty"):
        AppConfig.model_validate(raw)


def test_end_date_cannot_precede_start_date() -> None:
    raw = {
        "project": {"name": "test"},
        "data": {
            "cache_dir": "cache",
            "start_date": "2020-01-02",
            "end_date": "2020-01-01",
        },
        "universe": {},
        "strategy": {"benchmark": "000300.SH"},
        "factors": {"weights": {"momentum": 1.0}},
        "backtest": {},
        "reports": {"output_dir": "reports"},
    }

    with pytest.raises(ValidationError, match="end_date must be greater"):
        AppConfig.model_validate(raw)
