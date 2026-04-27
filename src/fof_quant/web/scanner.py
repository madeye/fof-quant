from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fof_quant.web.registry import RunRecord


def scan_reports_dir(reports_dir: Path) -> list[RunRecord]:
    """Scan a reports directory and return one RunRecord per discovered manifest.

    Recognized manifest filename patterns:
      broad_index_rebalance_<YYYYMMDD>.json  -> broad_index_signal
      broad_index_backtest_<YYYYMMDD>.json   -> broad_index_backtest
      artifact_manifest.json                 -> offline_pipeline

    The companion HTML report (if present) is linked via report_html_path.
    Records are idempotent: re-scanning the same artifact yields the same id.
    """
    if not reports_dir.exists():
        return []
    records: list[RunRecord] = []
    seen: set[str] = set()
    for path in sorted(reports_dir.rglob("*.json")):
        record = _record_from_manifest(path)
        if record is None or record.id in seen:
            continue
        seen.add(record.id)
        records.append(record)
    return records


def _record_from_manifest(path: Path) -> RunRecord | None:
    name = path.name
    kind: str | None = None
    html_name: str | None = None
    label: str
    as_of: str | None
    if name.startswith("broad_index_rebalance_") and name.endswith(".json"):
        kind = "broad_index_signal"
        stamp = name[len("broad_index_rebalance_") : -len(".json")]
        html_name = f"broad_index_signal_{stamp}.html"
        label = f"signal {stamp}"
        as_of = _isoformat_stamp(stamp)
    elif name.startswith("broad_index_backtest_") and name.endswith(".json"):
        kind = "broad_index_backtest"
        stamp = name[len("broad_index_backtest_") : -len(".json")]
        html_name = f"broad_index_backtest_{stamp}.html"
        label = f"backtest {stamp}"
        as_of = _isoformat_stamp(stamp)
    elif name == "artifact_manifest.json":
        kind = "offline_pipeline"
        label = f"offline {path.parent.name}"
        as_of = _read_offline_as_of(path)
        html_name = None
    else:
        return None

    output_dir = path.parent
    html_path: Path | None = None
    if html_name is not None:
        candidate = output_dir / html_name
        if candidate.exists():
            html_path = candidate

    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    record_id = _hash_id(kind, str(output_dir), name)
    return RunRecord(
        id=record_id,
        kind=kind,
        label=label,
        as_of_date=as_of,
        output_dir=str(output_dir),
        manifest_path=str(path),
        report_html_path=str(html_path) if html_path else None,
        status="completed",
        created_at=created_at,
    )


def _isoformat_stamp(stamp: str) -> str | None:
    if len(stamp) != 8 or not stamp.isdigit():
        return None
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"


def _read_offline_as_of(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(artifacts, dict):
        return None
    factor_path = artifacts.get("factor_snapshots")
    if not isinstance(factor_path, str):
        return None
    candidate = Path(factor_path).name
    for token in candidate.split("_"):
        token = token.split(".")[0]
        if len(token) == 8 and token.isdigit():
            return _isoformat_stamp(token)
    return None


def _hash_id(kind: str, output_dir: str, manifest_filename: str) -> str:
    digest = hashlib.sha1(
        f"{kind}|{output_dir}|{manifest_filename}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return digest[:16]
