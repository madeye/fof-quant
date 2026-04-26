# ETF FOF Implementation Checklist

## Repo Scaffold

- [ ] Create Python package structure for data, factors, allocation, backtest, reports, and CLI modules.
- [ ] Add project metadata and dependency management.
- [ ] Add formatter, linter, type checker, and test runner configuration.
- [ ] Create `configs/example.yaml` for the v1 CLI/report workflow.
- [ ] Add `.env.example` documenting `TUSHARE_TOKEN` and optional LLM credentials.
- [ ] Write a README with setup, config, and CLI examples.

## Configuration and CLI

- [ ] Define typed config models with defaults and validation errors.
- [ ] Implement `fof-quant config validate`.
- [ ] Implement `fof-quant data refresh`.
- [ ] Implement `fof-quant factors build`.
- [ ] Implement `fof-quant score`.
- [ ] Implement `fof-quant allocate`.
- [ ] Implement `fof-quant backtest`.
- [ ] Implement `fof-quant report`.
- [ ] Add structured logging and consistent exit codes.

## Data Interfaces

- [ ] Create provider interface for market, fund, index, calendar, holdings, and valuation data.
- [ ] Implement Tushare provider adapter.
- [ ] Add request retry, throttling, and provider error handling.
- [ ] Normalize ETF codes, stock codes, index codes, and trade dates.
- [ ] Implement raw and normalized cache layout.
- [ ] Add cache metadata with provider, fetch time, parameters, and schema version.
- [ ] Validate missing fields, duplicate keys, stale data, and date coverage.
- [ ] Add fixture datasets for offline tests.
- [ ] Add and maintain small real Tushare snapshot fixtures for offline provider normalization tests.

## Universe and Eligibility

- [ ] Define configurable 场内宽基指数基金 universe rules.
- [ ] Implement listing status and fund age filters.
- [ ] Implement liquidity and minimum data coverage filters.
- [ ] Implement manual include/exclude lists.
- [ ] Save inclusion and exclusion reason tables.
- [ ] Add tests for eligibility edge cases.

## Stock-Through Factor Engine

- [ ] Build ETF exposure resolver from disclosed holdings.
- [ ] Build fallback exposure resolver from index constituents.
- [ ] Add point-in-time availability controls to avoid look-ahead bias.
- [ ] Implement underlying stock factor calculation.
- [ ] Aggregate stock factors into ETF-level exposures.
- [ ] Compute concentration, industry/sector, liquidity, volatility, value, quality, momentum, and size exposures.
- [ ] Persist factor snapshots by rebalance date.
- [ ] Add deterministic tests for weighted aggregation.

## ETF Scoring

- [ ] Implement cross-sectional winsorization and normalization.
- [ ] Implement configurable factor weights.
- [ ] Build score contribution tables.
- [ ] Add rank output with eligibility, factor, and score columns.
- [ ] Add tests for normalization, missing factor handling, and tie behavior.

## Allocation

- [ ] Implement top-ranked candidate selection.
- [ ] Implement max ETF weight, min holdings, cash buffer, and turnover constraints.
- [ ] Add allocation solver or deterministic heuristic consistent with v1 requirements.
- [ ] Produce target holdings and rebalance trade lists.
- [ ] Generate deterministic allocation-change explanations.
- [ ] Add tests for constraint satisfaction.

## Backtest

- [ ] Implement rebalance calendar generation.
- [ ] Implement point-in-time strategy runner.
- [ ] Simulate trades, holdings, cash, fees, slippage, and unavailable prices.
- [ ] Calculate NAV, daily returns, drawdowns, turnover, and benchmark-relative series.
- [ ] Calculate annualized return, volatility, Sharpe ratio, Calmar ratio, max drawdown, tracking error, and win rate.
- [ ] Save holdings, trades, portfolio state, metrics, and charts data.
- [ ] Add accounting and metric regression tests.

## Reports

- [ ] Define report artifact directory structure.
- [ ] Generate Excel workbook with config, data coverage, universe, rankings, allocation, backtest metrics, holdings, and trades.
- [ ] Generate HTML report with tables, charts, risk notes, and benchmark comparison.
- [ ] Add report rendering checks for required sections.
- [ ] Ensure reports are reproducible from cached inputs.

## Optional LLM Explanations

- [ ] Keep LLM disabled by default.
- [ ] Add prompt templates for factor driver summaries, allocation-change summaries, and risk notes.
- [ ] Ensure LLM text never feeds back into scores, weights, or backtest calculations.
- [ ] Label generated text as narrative assistance, not investment advice.
- [ ] Add snapshot tests or golden-file checks for prompt payload construction.

## Testing and Quality

- [ ] Prioritize deterministic unit tests for date handling, factor math, allocation constraints, and metrics.
- [ ] Add integration tests using fixture data and local cache only.
- [ ] Add CLI smoke tests for each command.
- [ ] Add failure tests for missing config, missing token, invalid symbols, and insufficient data.
- [ ] Add CI workflow after the initial scaffold exists.
- [ ] Track any live Tushare smoke tests separately from offline CI tests.

## Documentation

- [ ] Document factor definitions and data availability assumptions.
- [ ] Document holdings disclosure lag and look-ahead-bias controls.
- [ ] Document backtest assumptions for costs, slippage, and missing data.
- [ ] Document report fields and interpretation guidance.
- [ ] Keep future Web dashboard notes in roadmap only until v1 stabilizes.
