# ETF FOF Implementation Checklist

> **Status note (2026-04-27):** Phase 6.5 (operational broad-index
> pipeline) is complete: `fof-quant pipeline broad-index` produces a
> real rebalance signal, JSON manifest, and Chinese Excel/HTML report
> from cached broad-index data. The formal stock-through `pipeline run`
> path still feeds engines empty inputs and is parked behind Phase 2
> (real stock-factor source). Engine-level boxes below describe the
> code in place and remain valid.

## Operational Pipeline (broad-index)

- [x] Take a current-holdings file (`holdings.json`) as input.
- [x] Build target `AllocationPlan` from sleeve picks + sleeve weight map.
- [x] Compute drift (current vs target) per sleeve.
- [x] Apply band-rebalance rule (±5pp absolute, ±25% relative, semi-annual force).
- [x] Emit trade list (notional + share counts at last NAV/close).
- [x] Write JSON manifest + Excel/HTML report from the trade list.
- [x] Add `fof-quant pipeline broad-index --current holdings.json` CLI.
- [x] Add tests for drift math and band-rebalance edge cases.

## Repo Scaffold

- [x] Create Python package structure for data, factors, allocation, backtest, reports, and CLI modules.
- [x] Add project metadata and dependency management.
- [x] Add formatter, linter, type checker, and test runner configuration.
- [x] Create `configs/example.yaml` for the v1 CLI/report workflow.
- [x] Add `.env.example` documenting `TUSHARE_TOKEN` and optional LLM credentials.
- [x] Write a README with setup, config, and CLI examples.

## Configuration and CLI

- [x] Define typed config models with defaults and validation errors.
- [x] Implement `fof-quant config validate`.
- [x] Implement `fof-quant data refresh`.
- [x] Implement `fof-quant factors build`.
- [x] Implement `fof-quant score`.
- [x] Implement `fof-quant allocate`.
- [x] Implement `fof-quant backtest`.
- [x] Implement `fof-quant report`.
- [x] Add structured logging and consistent exit codes.

## Data Interfaces

- [x] Create provider interface for market, fund, index, calendar, holdings, and valuation data.
- [x] Implement Tushare provider adapter.
- [x] Add request retry, throttling, and provider error handling.
- [x] Normalize ETF codes, stock codes, index codes, and trade dates.
- [x] Implement raw and normalized cache layout.
- [x] Add cache metadata with provider, fetch time, parameters, and schema version.
- [x] Validate missing fields, duplicate keys, stale data, and date coverage.
- [x] Add fixture datasets for offline tests.
- [x] Add and maintain small real Tushare snapshot fixtures for offline provider normalization tests.

## Universe and Eligibility

- [x] Define configurable 场内宽基指数基金 universe rules.
- [x] Implement listing status and fund age filters.
- [x] Implement liquidity and minimum data coverage filters.
- [x] Implement manual include/exclude lists.
- [x] Save inclusion and exclusion reason tables.
- [x] Add tests for eligibility edge cases.

## Stock-Through Factor Engine

- [x] Build ETF exposure resolver from disclosed holdings.
- [x] Build fallback exposure resolver from index constituents.
- [x] Add point-in-time availability controls to avoid look-ahead bias.
- [x] Implement underlying stock factor calculation.
- [x] Aggregate stock factors into ETF-level exposures.
- [x] Compute concentration, industry/sector, liquidity, volatility, value, quality, momentum, and size exposures.
- [x] Persist factor snapshots by rebalance date.
- [x] Add deterministic tests for weighted aggregation.

## ETF Scoring

- [x] Implement cross-sectional winsorization and normalization.
- [x] Implement configurable factor weights.
- [x] Build score contribution tables.
- [x] Add rank output with eligibility, factor, and score columns.
- [x] Add tests for normalization, missing factor handling, and tie behavior.

## Allocation

- [x] Implement top-ranked candidate selection.
- [x] Implement max ETF weight, min holdings, cash buffer, and turnover constraints.
- [x] Add allocation solver or deterministic heuristic consistent with v1 requirements.
- [x] Produce target holdings and rebalance trade lists.
- [x] Generate deterministic allocation-change explanations.
- [x] Add tests for constraint satisfaction.

## Backtest

- [x] Implement rebalance calendar generation.
- [x] Implement point-in-time strategy runner.
- [x] Simulate trades, holdings, cash, fees, slippage, and unavailable prices.
- [x] Calculate NAV, daily returns, drawdowns, turnover, and benchmark-relative series.
- [x] Calculate annualized return, volatility, Sharpe ratio, Calmar ratio, max drawdown, tracking error, and win rate.
- [x] Save holdings, trades, portfolio state, metrics, and charts data.
- [x] Add accounting and metric regression tests.

## Reports

- [x] Define report artifact directory structure.
- [x] Generate Excel workbook with config, data coverage, universe, rankings, allocation, backtest metrics, holdings, and trades.
- [x] Generate HTML report with tables, charts, risk notes, and benchmark comparison.
- [x] Add report rendering checks for required sections.
- [x] Ensure reports are reproducible from cached inputs.

## Optional LLM Explanations

- [x] Keep LLM disabled by default.
- [x] Add prompt templates for factor driver summaries, allocation-change summaries, and risk notes.
- [x] Ensure LLM text never feeds back into scores, weights, or backtest calculations.
- [x] Label generated text as narrative assistance, not investment advice.
- [x] Add snapshot tests or golden-file checks for prompt payload construction.

## Testing and Quality

- [x] Prioritize deterministic unit tests for date handling, factor math, allocation constraints, and metrics.
- [x] Add integration tests using fixture data and local cache only.
- [x] Add CLI smoke tests for each command.
- [x] Add failure tests for missing config, missing token, invalid symbols, and insufficient data.
- [x] Add CI workflow after the initial scaffold exists.
- [x] Track any live Tushare smoke tests separately from offline CI tests.

## Documentation

- [x] Document factor definitions and data availability assumptions.
- [x] Document holdings disclosure lag and look-ahead-bias controls.
- [x] Document backtest assumptions for costs, slippage, and missing data.
- [x] Document report fields and interpretation guidance.
- [x] Keep future Web dashboard notes in roadmap only until v1 stabilizes.
