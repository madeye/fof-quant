from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class CurrentPosition:
    ts_code: str
    shares: float


@dataclass(frozen=True)
class CurrentPortfolio:
    as_of: date
    cash_cny: float
    positions: list[CurrentPosition]

    @classmethod
    def empty(cls, as_of: date, cash_cny: float) -> CurrentPortfolio:
        return cls(as_of=as_of, cash_cny=cash_cny, positions=[])

    def total_aum(self, last_price: dict[str, float]) -> float:
        market = sum(p.shares * last_price[p.ts_code] for p in self.positions)
        return market + self.cash_cny

    def weights(self, last_price: dict[str, float]) -> dict[str, float]:
        aum = self.total_aum(last_price)
        if aum <= 0:
            return {}
        return {p.ts_code: p.shares * last_price[p.ts_code] / aum for p in self.positions}


def load_holdings(path: Path) -> CurrentPortfolio:
    raw = json.loads(path.read_text(encoding="utf-8"))
    as_of = _parse_date(raw["as_of"])
    cash_cny = float(raw.get("cash_cny", 0.0))
    positions = [
        CurrentPosition(ts_code=str(item["ts_code"]), shares=float(item["shares"]))
        for item in raw.get("positions", [])
    ]
    return CurrentPortfolio(as_of=as_of, cash_cny=cash_cny, positions=positions)


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse as_of date {value!r}; use YYYY-MM-DD or YYYYMMDD")
