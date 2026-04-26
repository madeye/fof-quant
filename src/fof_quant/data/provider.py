from __future__ import annotations

from collections.abc import Collection
from datetime import date
from typing import Any, Protocol

from pydantic import BaseModel, Field

JsonRecord = dict[str, Any]


class DataRequest(BaseModel):
    dataset: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    symbols: list[str] = Field(default_factory=list)
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class DataTable(BaseModel):
    dataset: str = Field(min_length=1)
    rows: list[JsonRecord]

    def validate_required_fields(self, required_fields: Collection[str]) -> None:
        missing_by_row: list[str] = []
        for index, row in enumerate(self.rows):
            missing = sorted(field for field in required_fields if field not in row)
            if missing:
                missing_by_row.append(f"row {index}: {', '.join(missing)}")
        if missing_by_row:
            details = "; ".join(missing_by_row)
            raise ValueError(f"missing required fields in {self.dataset}: {details}")

    def validate_unique_key(self, key_fields: tuple[str, ...]) -> None:
        seen: set[tuple[Any, ...]] = set()
        duplicates: list[tuple[Any, ...]] = []
        for row in self.rows:
            key = tuple(row.get(field) for field in key_fields)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            raise ValueError(f"duplicate keys in {self.dataset}: {duplicates[:5]}")


class DataProvider(Protocol):
    name: str

    def fetch(self, request: DataRequest) -> DataTable:
        """Fetch a normalized data table for the request."""
