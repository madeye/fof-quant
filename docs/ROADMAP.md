# ETF FOF Roadmap

## Phase 0: Project Scaffold and Config

**Goal:** Establish a maintainable Python project foundation.

- Create package layout, CLI entry point, test structure, and development tooling.
- Define versioned config schema for data, universe, factors, allocation, backtest, and report settings.
- Add example config for 场内宽基指数基金增强 FOF research.
- Set up deterministic fixtures for unit and integration tests.
- Document environment setup, Tushare token configuration, and common commands.

**Status:** Engine and artifacts implemented; not yet driven by `pipeline.py`, which still passes empty inputs through this engine.

**Exit criteria:** The project installs locally, CLI help works, config validation is tested, and fixture-based tests run without external services.

## Phase 1: Tushare Data Layer and Cache

**Goal:** Build reliable data ingestion and normalized local storage.

- Implement Tushare client wrapper with request throttling, retries, and clear errors.
- Fetch trading calendar, ETF metadata, ETF prices, NAV, index prices, index constituents, and available holdings data.
- Normalize symbols, dates, numeric fields, and provider-specific naming.
- Store raw and normalized cache files with data version metadata.
- Add validation reports for coverage, missing values, duplicates, and stale data.
- Keep a small real Tushare snapshot fixture in tests so provider normalization is checked against actual API output without requiring live credentials in CI.

**Status:** Implemented end-to-end for the broad-index sleeves used by `analyze csi300` and `analyze broad-index`. The generic `data refresh` CLI path still calls `etf_daily` without per-symbol iteration, which Tushare rejects in practice; live use today goes through the broad-index fetcher instead.

**Exit criteria:** Data refresh and cache-read commands work for a small configured universe, and fixture tests validate normalization behavior against both synthetic cases and a real Tushare snapshot.

## Phase 2: Stock-Through Factor Engine

**Goal:** Convert ETF/index holdings into transparent factor exposures.

- Build exposure resolver using disclosed ETF holdings first and index constituents as fallback.
- Implement point-in-time safeguards for holdings and constituent availability.
- Compute underlying stock factors and aggregate them into ETF-level factor snapshots.
- Add industry/sector, concentration, liquidity, and style exposure tables.
- Persist factor snapshots by rebalance date for audit and reuse.

**Status:** Engine and artifacts implemented; not yet driven by `pipeline.py`, which still passes empty inputs through this engine.

**Exit criteria:** A rebalance date can produce ETF factor tables with traceable underlying stock contributions and tested aggregation math.

## Phase 3: ETF Scoring and Allocation

**Goal:** Produce candidate rankings and FOF target weights.

- Implement eligibility filters for fund age, liquidity, listing status, data coverage, and exclusion lists.
- Normalize factor exposures cross-sectionally and combine them with configurable weights.
- Generate ETF rankings with score breakdowns and filter reasons.
- Implement allocation constraints including max weight, min holdings, turnover, and cash buffer.
- Export target holdings and deterministic allocation explanations.

**Status:** Engine and artifacts implemented; not yet driven by `pipeline.py`, which still passes empty inputs through this engine.

**Exit criteria:** The CLI can generate a target allocation for a configured date with constraint checks and score attribution.

## Phase 4: Backtest Engine and Metrics

**Goal:** Validate strategies historically with realistic assumptions.

- Build rebalance scheduler and point-in-time data loader.
- Simulate trades, holdings, cash, transaction costs, slippage, and unavailable prices.
- Calculate NAV curve, drawdowns, benchmark-relative returns, turnover, and risk metrics.
- Save holdings, trades, daily portfolio state, and metrics as artifacts.
- Add regression tests for portfolio accounting and metric formulas.

**Status:** Engine and artifacts implemented; not yet driven by `pipeline.py`, which still passes empty inputs through this engine.

**Exit criteria:** A historical backtest produces reproducible outputs and passes fixture-based accounting tests.

## Phase 5: Reports and LLM Explanations

**Goal:** Make outputs reviewable by analysts and investment stakeholders.

- Generate Excel workbooks with config, data coverage, universe, rankings, allocation, backtest metrics, holdings, and trades.
- Generate HTML reports with readable tables, charts, risk notes, and benchmark comparisons.
- Add optional LLM explanations for allocation changes, factor drivers, and risk summaries.
- Clearly label LLM text as narrative assistance and keep it outside core calculations.
- Add report rendering checks for required sections and artifact paths.

**Status:** Engine and artifacts implemented; not yet driven by `pipeline.py`, which still passes empty inputs through this engine.

**Exit criteria:** A full pipeline run creates complete Excel and HTML reports from cached data, with optional LLM text disabled by default.

## Phase 6.5: Operational Pipeline

**Goal:** Make `fof-quant pipeline ...` produce a real monthly rebalance signal from cached broad-index data, not from empty inputs.

- Take a current-holdings file (`holdings.json`) as input.
- Reuse `analysis/broad_index._rank_sleeve` to pick one ETF per sleeve.
- Build a target `AllocationPlan` from a configurable sleeve-weight map.
- Compute drift (current vs target) and apply the band-rebalance rule (±5pp absolute or ±25% relative; forced semi-annual rebalance).
- Emit a trade list (notional + share counts at last NAV/close) and a JSON manifest alongside the existing Excel/HTML report.
- Keep the formal stock-through `pipeline.py` path untouched until Phase 2 has a real stock-factor source.

**Status:** Done. `pipeline_broad_index.run_broad_index_pipeline` plus `portfolio.holdings` / `portfolio.rebalance` deliver the operational signal; walk-forward backtest, sleeve attribution, and Chinese Excel/HTML reports landed on top. Stock-through `pipeline.py` remains intentionally pass-through pending Phase 2.

**Exit criteria:** `fof-quant pipeline broad-index --current holdings.json -c configs/broad_index.yaml` produces an Excel + manifest with a non-empty trade list and explicit constraint checks.

## Phase 7: Future Web Dashboard


**Goal:** Explore an interactive UI only after the CLI/report workflow is stable.

- Define dashboard use cases from real report review workflows.
- Add pages for universe inspection, factor drill-down, allocation review, and backtest comparison.
- Reuse the same calculation artifacts and APIs created for CLI reports.
- Keep Web functionality separate from v1 acceptance criteria until requirements are validated.

**Status:** Implemented as an artifact manifest for a future dashboard reader; no interactive dashboard is in v1.

**Exit criteria:** A dashboard prototype can read existing artifacts without changing core calculation logic.
