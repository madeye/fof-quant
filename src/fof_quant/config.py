from datetime import date
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, Field, PositiveFloat, field_validator


class ProjectConfig(BaseModel):
    name: str = Field(min_length=1)
    timezone: str = "Asia/Shanghai"


class DataConfig(BaseModel):
    provider: Literal["tushare"] = "tushare"
    cache_dir: Path
    start_date: date
    end_date: date | None = None

    @field_validator("end_date")
    @classmethod
    def end_date_must_not_precede_start(
        cls, value: date | None, info: object
    ) -> date | None:
        if value is None:
            return value
        data = getattr(info, "data", {})
        start_date = data.get("start_date")
        if start_date is not None and value < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return value


class UniverseConfig(BaseModel):
    fund_types: list[str] = Field(default_factory=lambda: ["broad_index_etf"])
    min_listing_days: int = Field(default=252, ge=0)
    min_avg_daily_amount: PositiveFloat = 50_000_000
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    rebalance_frequency: Literal["weekly", "monthly", "quarterly"] = "monthly"
    benchmark: str
    cash_buffer: float = Field(default=0.01, ge=0.0, lt=1.0)
    max_weight: float = Field(default=0.2, gt=0.0, le=1.0)
    min_holdings: int = Field(default=5, ge=1)
    turnover_limit: float = Field(default=0.5, ge=0.0, le=1.0)


class FactorsConfig(BaseModel):
    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def weights_must_not_be_empty(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("factor weights must not be empty")
        return value


class BacktestConfig(BaseModel):
    initial_cash: PositiveFloat = 1_000_000
    transaction_cost_bps: float = Field(default=2.0, ge=0.0)
    slippage_bps: float = Field(default=1.0, ge=0.0)


class ReportsConfig(BaseModel):
    output_dir: Path
    formats: list[Literal["excel", "html"]] = Field(
        default_factory=lambda: cast(list[Literal["excel", "html"]], ["excel", "html"])
    )
    llm_explanations: bool = False


class AppConfig(BaseModel):
    project: ProjectConfig
    data: DataConfig
    universe: UniverseConfig
    strategy: StrategyConfig
    factors: FactorsConfig
    backtest: BacktestConfig
    reports: ReportsConfig


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    return AppConfig.model_validate(raw)
