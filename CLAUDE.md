# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

Toolchain is `uv` + Python ≥3.11. Strict mypy is enforced.

```bash
uv sync --extra dev                                     # install (dev deps)
uv run fof-quant --help                                 # CLI entry (Typer)
uv run fof-quant config validate -c configs/example.yaml
uv run fof-quant pipeline run     -c configs/example.yaml
uv run fof-quant data refresh     -c configs/example.yaml --dry-run

uv run ruff check .                                     # lint
uv run mypy src tests                                   # strict type check
uv run pytest                                           # full suite
uv run pytest tests/test_pipeline.py::test_x -q         # single test
```

The pre-push gate (per global workflow rule) is `ruff check . && mypy src tests && pytest`.

## Big-picture architecture

This is a **deterministic offline research pipeline** for 场内宽基指数基金 (broad-index ETF) FOF construction. v1 is CLI + reports only — no live trading, no web UI, no intraday data, and **LLMs never participate in scoring, weighting, or backtest math** (they only annotate finished reports). See `docs/PRD.md`, `docs/ROADMAP.md`, `docs/TODO.md`.

Single Typer app at `fof_quant.cli:app` exposes subcommand groups that mirror the package layout — each group is a thin shell around one engine module:

```
config validate      → config.load_config (pydantic AppConfig from YAML)
data refresh         → data.tushare → data.provider → data.refresh → data.cache
factors build        → factors.engine.FactorEngine (uses ExposureResolver)
score run            → scoring.engine.ScoringEngine
allocate run         → allocation.engine.AllocationEngine → AllocationPlan
backtest run         → backtest.engine.BacktestEngine (+ metrics, schedule)
report                → reports.generator.ReportGenerator (xlsx + html, optional LLM narrative)
pipeline run         → pipeline.run_offline_pipeline (orchestrates all of the above)
```

Data flow per rebalance: **Tushare → normalized cache → universe eligibility filter → stock-through factor exposures → ETF score → allocation plan (with cash buffer / max weight / min holdings constraints) → backtest result → Excel + HTML report → `artifact_manifest.json`** under `reports.output_dir`. Each stage has an `artifacts.py` writer; the manifest is the canonical join key between stages.

Key boundaries to preserve when editing:

- **Provider abstraction.** `data.provider.DataProvider` is the seam; `data.tushare` is the only adapter today, but `data.normalization` and `data.datasets` (dataset specs + `DEFAULT_DATASETS` tuple) are provider-agnostic. New data sources go behind `DataProvider`, not inside `tushare.py`.
- **Stock-through exposure.** `factors.exposure.ExposureResolver` resolves an ETF to underlying `Holding`s using disclosed fund holdings when present and index constituents as fallback — `FactorEngine` only does the weighted aggregation. Don't push lookup logic into the engine.
- **Config is the contract.** `config.AppConfig` (pydantic v2, strict) is the single source of truth for `project / data / universe / strategy / factors / backtest / reports` settings — every CLI command takes `--config` and re-loads it. New tunables go on these models, not as CLI flags or module constants.
- **Determinism.** Calculations must be reproducible from `(config, cache, snapshot)`. `tests/test_real_tushare_snapshot.py` pins normalization against a recorded Tushare payload; `tests/test_secret_hygiene.py` pins `.env` policy. Don't break either.

## Secrets / env

`.env` (gitignored) provides `TUSHARE_TOKEN` (required for live `data refresh`) and optional `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_API_BASE` consumed via `fof_quant.env.llm_env()`. `.env.example` must keep secret keys empty (enforced by `test_secret_hygiene.py`). Provider defaults (model + base URL) are baked into `env._LLM_DEFAULTS` for openai / claude / minimax / kimi.
