from __future__ import annotations

from datetime import date
from typing import Any

from fof_quant.data.datasets import DatasetSpec
from fof_quant.data.provider import DataTable, JsonRecord


def normalize_rows(dataset: DatasetSpec, rows: list[JsonRecord]) -> DataTable:
    normalized = [_normalize_row(row) for row in rows]
    normalized.sort(key=lambda row: _sort_key(dataset, row))
    table = DataTable(dataset=dataset.name, rows=normalized)
    table.validate_required_fields(dataset.required_fields)
    table.validate_unique_key(dataset.unique_key)
    return table


def request_params(
    *,
    dataset: DatasetSpec,
    start_date: date | None,
    end_date: date | None,
    symbols: list[str],
    params: dict[str, str | int | float | bool | None],
) -> dict[str, str | int | float | bool]:
    output: dict[str, str | int | float | bool] = {
        key: value for key, value in params.items() if value is not None
    }
    if start_date is not None:
        output["start_date"] = _date_to_tushare(start_date)
    if end_date is not None:
        output["end_date"] = _date_to_tushare(end_date)
    if symbols and dataset.symbol_field is not None:
        output[dataset.symbol_field] = ",".join(symbols)
    return output


def _normalize_row(row: JsonRecord) -> JsonRecord:
    output: JsonRecord = {}
    for key, value in row.items():
        if value is None:
            continue
        output[key] = _normalize_value(value)
    return output


def _normalize_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _sort_key(dataset: DatasetSpec, row: JsonRecord) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in dataset.unique_key)


def _date_to_tushare(value: date) -> str:
    return value.strftime("%Y%m%d")
