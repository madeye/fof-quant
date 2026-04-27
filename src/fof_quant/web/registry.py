from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    as_of_date TEXT,
    output_dir TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    report_html_path TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL,
    config_yaml TEXT
);
CREATE INDEX IF NOT EXISTS runs_kind_as_of ON runs(kind, as_of_date);
"""


@dataclass(frozen=True)
class RunRecord:
    id: str
    kind: str
    label: str
    as_of_date: str | None
    output_dir: str
    manifest_path: str
    report_html_path: str | None
    status: str
    created_at: str
    config_yaml: str | None = None


class RunRegistry:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_many(self, records: Iterable[RunRecord]) -> int:
        rows = [
            (
                r.id,
                r.kind,
                r.label,
                r.as_of_date,
                r.output_dir,
                r.manifest_path,
                r.report_html_path,
                r.status,
                r.created_at,
                r.config_yaml,
            )
            for r in records
        ]
        if not rows:
            return 0
        with closing(self._connect()) as conn:
            cur = conn.executemany(
                """
                INSERT INTO runs (
                    id, kind, label, as_of_date, output_dir,
                    manifest_path, report_html_path, status, created_at, config_yaml
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind=excluded.kind,
                    label=excluded.label,
                    as_of_date=excluded.as_of_date,
                    output_dir=excluded.output_dir,
                    manifest_path=excluded.manifest_path,
                    report_html_path=excluded.report_html_path,
                    status=excluded.status,
                    created_at=excluded.created_at,
                    config_yaml=excluded.config_yaml
                """,
                rows,
            )
            conn.commit()
            return cur.rowcount

    def list(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        sql = "SELECT * FROM runs"
        params: list[object] = []
        if kind:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with closing(self._connect()) as conn:
            cur = conn.execute(sql, params)
            return [_row_to_record(row) for row in cur.fetchall()]

    def get(self, run_id: str) -> RunRecord | None:
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cur.fetchone()
        return _row_to_record(row) if row else None

    def count(self) -> int:
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM runs")
            return int(cur.fetchone()[0])


def _row_to_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=row["id"],
        kind=row["kind"],
        label=row["label"],
        as_of_date=row["as_of_date"],
        output_dir=row["output_dir"],
        manifest_path=row["manifest_path"],
        report_html_path=row["report_html_path"],
        status=row["status"],
        created_at=row["created_at"],
        config_yaml=row["config_yaml"],
    )
