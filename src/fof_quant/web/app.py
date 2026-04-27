from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fof_quant.web.registry import RunRegistry
from fof_quant.web.routes.runs import router as runs_router
from fof_quant.web.scanner import scan_reports_dir


def create_app(*, reports_dir: Path, db_path: Path, scan_on_boot: bool = True) -> FastAPI:
    app = FastAPI(title="fof-quant dashboard", version="1.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    registry = RunRegistry(db_path)
    if scan_on_boot:
        registry.upsert_many(scan_reports_dir(reports_dir))
    app.state.registry = registry
    app.state.reports_dir = str(reports_dir)
    app.include_router(runs_router)
    return app
