from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fof_quant.data.provider import DataRequest, DataTable


class CacheMetadata(BaseModel):
    dataset: str
    provider: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    schema_version: int = 1
    request: DataRequest
    row_count: int


class CacheStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.normalized_dir = root / "normalized"
        self.metadata_dir = root / "metadata"

    def ensure_dirs(self) -> None:
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def write_table(self, table: DataTable, metadata: CacheMetadata) -> None:
        if table.dataset != metadata.dataset:
            raise ValueError("table and metadata dataset names differ")
        self.ensure_dirs()
        self._table_path(table.dataset).write_text(
            json.dumps(table.model_dump(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._metadata_path(table.dataset).write_text(
            metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def read_table(self, dataset: str) -> DataTable:
        payload = self._read_json(self._table_path(dataset))
        return DataTable.model_validate(payload)

    def read_metadata(self, dataset: str) -> CacheMetadata:
        payload = self._read_json(self._metadata_path(dataset))
        return CacheMetadata.model_validate(payload)

    def exists(self, dataset: str) -> bool:
        return self._table_path(dataset).exists() and self._metadata_path(dataset).exists()

    def _table_path(self, dataset: str) -> Path:
        return self.normalized_dir / f"{dataset}.json"

    def _metadata_path(self, dataset: str) -> Path:
        return self.metadata_dir / f"{dataset}.json"

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
