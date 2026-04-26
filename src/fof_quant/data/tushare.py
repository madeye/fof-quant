from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from fof_quant.data.datasets import dataset_spec
from fof_quant.data.normalization import normalize_rows, request_params
from fof_quant.data.provider import DataRequest, DataTable, JsonRecord
from fof_quant.env import tushare_token


class TushareClient(Protocol):
    def query(self, api_name: str, **params: object) -> Any:
        """Run a Tushare API query and return a dataframe-like object or records."""


class TushareProvider:
    name = "tushare"

    def __init__(
        self,
        client: TushareClient,
        *,
        min_interval_seconds: float = 0.3,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.sleep = sleep
        self._last_call_at = 0.0

    def fetch(self, request: DataRequest) -> DataTable:
        spec = dataset_spec(request.dataset)
        params = request_params(
            dataset=spec,
            start_date=request.start_date,
            end_date=request.end_date,
            symbols=request.symbols,
            params=request.params,
        )
        rows = self._query_with_retries(spec.tushare_api, params)
        return normalize_rows(spec, rows)

    def _query_with_retries(
        self, api_name: str, params: dict[str, str | int | float | bool]
    ) -> list[JsonRecord]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = self.client.query(api_name, **params)
                return _records_from_response(response)
            except Exception as exc:  # pragma: no cover - branch exercised via fake failures
                last_error = exc
                if attempt == self.max_retries:
                    break
                self.sleep(float(attempt))
        message = f"Tushare API call failed after {self.max_retries} attempts"
        raise RuntimeError(message) from last_error

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call_at
        if self._last_call_at > 0 and elapsed < self.min_interval_seconds:
            self.sleep(self.min_interval_seconds - elapsed)
        self._last_call_at = time.monotonic()


def build_tushare_provider() -> TushareProvider:
    token = tushare_token()
    if not token:
        raise ValueError("Tushare token is not configured; set TUSHARE_TOKEN in .env or shell")
    try:
        import tushare as ts  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("tushare package is required for live data refresh") from exc
    return TushareProvider(ts.pro_api(token))


def _records_from_response(response: Any) -> list[JsonRecord]:
    records = response.to_dict(orient="records") if hasattr(response, "to_dict") else response
    if not isinstance(records, list):
        raise TypeError("Tushare response must be dataframe-like or a list of records")
    if not all(isinstance(record, dict) for record in records):
        raise TypeError("Tushare response records must be mappings")
    return records
