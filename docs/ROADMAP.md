# ETF FOF Roadmap

## Phase 0: Project Scaffold and Config

**Goal:** Establish a maintainable Python project foundation.

- Create package layout, CLI entry point, test structure, and development tooling.
- Define versioned config schema for data, universe, factors, allocation, backtest, and report settings.
- Add example config for 场内宽基指数基金增强 FOF research.
- Set up deterministic fixtures for unit and integration tests.
- Document environment setup, Tushare token configuration, and common commands.

**Status:** Implemented.

**Exit criteria:** The project installs locally, CLI help works, config validation is tested, and fixture-based tests run without external services.

## Phase 1: Tushare Data Layer and Cache

**Goal:** Build reliable data ingestion and normalized local storage.

- Implement Tushare client wrapper with request throttling, retries, and clear errors.
- Fetch trading calendar, ETF metadata, ETF prices, NAV, index prices, index constituents, and available holdings data.
- Normalize symbols, dates, numeric fields, and provider-specific naming.
- Store raw and normalized cache files with data version metadata.
- Add validation reports for coverage, missing values, duplicates, and stale data.
- Keep a small real Tushare snapshot fixture in tests so provider normalization is checked against actual API output without requiring live credentials in CI.

**Status:** Implemented for the provider/cache boundary, offline fixture validation, and live refresh entry point.

**Exit criteria:** Data refresh and cache-read commands work for a small configured universe, and fixture tests validate normalization behavior against both synthetic cases and a real Tushare snapshot.

## Phase 2: Stock-Through Factor Engine

**Goal:** Convert ETF/index holdings into transparent factor exposures.

- Build exposure resolver using disclosed ETF holdings first and index constituents as fallback.
- Implement point-in-time safeguards for holdings and constituent availability.
- Compute underlying stock factors and aggregate them into ETF-level factor snapshots.
- Add industry/sector, concentration, liquidity, and style exposure tables.
- Persist factor snapshots by rebalance date for audit and reuse.

**Status:** Implemented.

**Exit criteria:** A rebalance date can produce ETF factor tables with traceable underlying stock contributions and tested aggregation math.

## Phase 3: ETF Scoring and Allocation

**Goal:** Produce candidate rankings and FOF target weights.

- Implement eligibility filters for fund age, liquidity, listing status, data coverage, and exclusion lists.
- Normalize factor exposures cross-sectionally and combine them with configurable weights.
- Generate ETF rankings with score breakdowns and filter reasons.
- Implement allocation constraints including max weight, min holdings, turnover, and cash buffer.
- Export target holdings and deterministic allocation explanations.

**Status:** Implemented.

**Exit criteria:** The CLI can generate a target allocation for a configured date with constraint checks and score attribution.

## Phase 4: Backtest Engine and Metrics

**Goal:** Validate strategies historically with realistic assumptions.

- Build rebalance scheduler and point-in-time data loader.
- Simulate trades, holdings, cash, transaction costs, slippage, and unavailable prices.
- Calculate NAV curve, drawdowns, benchmark-relative returns, turnover, and risk metrics.
- Save holdings, trades, daily portfolio state, and metrics as artifacts.
- Add regression tests for portfolio accounting and metric formulas.

**Status:** Implemented.

**Exit criteria:** A historical backtest produces reproducible outputs and passes fixture-based accounting tests.

## Phase 5: Reports and LLM Explanations

**Goal:** Make outputs reviewable by analysts and investment stakeholders.

- Generate Excel workbooks with config, data coverage, universe, rankings, allocation, backtest metrics, holdings, and trades.
- Generate HTML reports with readable tables, charts, risk notes, and benchmark comparisons.
- Add optional LLM explanations for allocation changes, factor drivers, and risk summaries.
- Clearly label LLM text as narrative assistance and keep it outside core calculations.
- Add report rendering checks for required sections and artifact paths.

**Status:** Implemented.

**Exit criteria:** A full pipeline run creates complete Excel and HTML reports from cached data, with optional LLM text disabled by default.

## Phase 6: Future Web Dashboard

**Goal:** Explore an interactive UI only after the CLI/report workflow is stable.

- Define dashboard use cases from real report review workflows.
- Add pages for universe inspection, factor drill-down, allocation review, and backtest comparison.
- Reuse the same calculation artifacts and APIs created for CLI reports.
- Keep Web functionality separate from v1 acceptance criteria until requirements are validated.

**Status:** Implemented as an artifact manifest for a future dashboard reader; no interactive dashboard is in v1.

**Exit criteria:** A dashboard prototype can read existing artifacts without changing core calculation logic.
