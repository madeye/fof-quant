# ETF FOF Product Requirements

## 1. Product Summary

Build a v1 command-line and report-based ETF FOF system for 场内宽基指数基金增强 allocation. The system ingests Tushare market and fund data, performs 股票穿透增强 factor analysis through ETF holdings and index constituents, scores candidate ETFs, builds allocation recommendations, backtests historical strategies, and exports Excel/HTML reports.

The first version is intentionally non-interactive: analysts run CLI commands, review deterministic outputs, and use optional LLM-generated explanations only for narrative interpretation and risk disclosure. A Web dashboard is a future phase, not part of v1 delivery.

## 2. Goals

- Create a repeatable pipeline from raw Tushare data to ETF FOF portfolio recommendations.
- Support transparent ETF scoring based on fund-level, index-level, and stock-through factors.
- Provide backtests with clear metrics, turnover, drawdown, and benchmark comparison.
- Export reviewable Excel and HTML reports for investment research workflows.
- Keep core calculations deterministic, testable, and independent from any LLM.

## 3. Non-Goals

- No live trading, order routing, or brokerage integration.
- No intraday strategy or real-time quote dependency in v1.
- No interactive Web dashboard in v1; v1.1 introduces a read-only dashboard that reads existing CLI artifacts without altering core calculations.
- No LLM-based portfolio construction, factor calculation, or trading decision logic.
- No modification of `../china-stock-multifactor`; it may be used only as a reference project.

## 4. Target Users

- Quant researchers who need to test ETF FOF allocation ideas.
- Portfolio analysts who need explainable ETF ranking and allocation reports.
- Investment reviewers who need reproducible backtest evidence and risk summaries.

## 5. Core Workflow

1. Configure Tushare token, cache path, universe rules, strategy parameters, and report output path.
2. Refresh local data cache for ETFs, index constituents, holdings, prices, NAV, valuation, and risk-free rate inputs where available.
3. Build stock-through exposures by mapping ETFs to underlying index or disclosed holdings.
4. Compute factors, scores, eligibility filters, and ranking outputs.
5. Generate FOF target allocation under configured constraints.
6. Run backtests over historical rebalance dates.
7. Export Excel/HTML reports with tables, charts, metrics, holdings, and explanations.

## 6. Functional Requirements

### 6.1 CLI

- Provide CLI commands for data refresh, factor calculation, scoring, allocation, backtest, and report generation.
- Support configuration through a versioned YAML or TOML file.
- Allow date range, rebalance frequency, universe, benchmark, and output directory overrides.
- Return non-zero exit codes on validation, data, or calculation failures.

### 6.2 Data Layer

- Integrate with Tushare for fund metadata, ETF prices, fund NAV, index constituents, index prices, trading calendar, and relevant financial/valuation data.
- Cache raw and normalized datasets locally to make repeated runs reproducible and efficient.
- Validate required fields, date coverage, missing values, duplicated rows, and symbol mapping.
- Keep data interfaces abstract enough to add alternative providers later.

### 6.3 Universe and Eligibility

- Focus v1 on 场内宽基指数基金 and related broad-market ETF products.
- Filter candidates by listing status, liquidity, age, tracking target, missing data, and configurable exclusion lists.
- Preserve audit tables explaining why funds were included or excluded.

### 6.4 Stock-Through Factor Engine

- Estimate ETF stock exposure using disclosed holdings when available and index constituents otherwise.
- Compute ETF-level factor exposures by aggregating underlying stock factors and weights.
- Support factors such as momentum, value, quality, volatility, size, liquidity, concentration, and industry/sector exposure.
- Record factor snapshots by date for auditability.

### 6.5 ETF Scoring and Allocation

- Normalize factor values cross-sectionally by rebalance date.
- Combine factors using configured weights into an ETF score.
- Apply risk and liquidity filters before allocation.
- Produce target FOF weights under constraints such as max ETF weight, min holding count, turnover limit, and cash buffer.
- Explain allocation changes using deterministic contribution tables.

### 6.6 Backtesting

- Run historical simulations over configurable rebalance schedules.
- Include transaction cost, slippage assumptions, suspended or missing price handling, and delayed availability rules.
- Output performance metrics including annualized return, volatility, Sharpe ratio, max drawdown, Calmar ratio, win rate, turnover, tracking error, and benchmark-relative return.
- Save portfolio holdings, trades, NAV curve, drawdown curve, and metric tables.

### 6.7 Reporting

- Generate Excel reports for detailed review and HTML reports for readable sharing.
- Include configuration summary, data coverage, ETF universe, rankings, target allocation, backtest metrics, charts, and risk notes.
- Make optional LLM explanations clearly labeled as narrative assistance, not investment advice or calculation inputs.
- Ensure reports can be regenerated from the same config and cache state.
- The HTML report remains the canonical per-run artifact; the v1.1 web dashboard is a review-and-compare surface layered on top of these artifacts and never mutates the underlying JSON manifests, Excel workbooks, or HTML reports.

## 7. Quality Requirements

- Deterministic calculations for the same inputs and configuration.
- Unit tests for factor math, allocation constraints, date handling, and metric calculation.
- Integration tests using small fixture datasets without requiring live Tushare access.
- Clear error messages for missing token, missing data, unsupported symbols, and invalid config.
- Structured logging for long-running data and backtest commands.

## 8. Acceptance Criteria

- A user can initialize config and run the full v1 pipeline from CLI.
- The system can refresh or read cached Tushare-derived data for a configured ETF universe.
- ETF ranking and allocation outputs include reproducible scores and constraint checks.
- A backtest run produces NAV, holdings, trades, metrics, and benchmark comparison artifacts.
- Excel and HTML reports render without broken tables or missing required sections.
- Tests cover deterministic business logic and pass without external network access.
- LLM explanations, if enabled, do not alter scores, weights, backtest results, or risk metrics.

## 9. Risks and Open Questions

- Tushare data availability and field coverage may vary by ETF, date, and account permission.
- ETF holdings disclosure lag must be modeled conservatively to avoid look-ahead bias.
- Index constituent and weight data may require provider-specific normalization.
- The exact broad-index ETF universe definition should remain configurable.
- v1.1 web dashboard scope is locked to a read-only run registry + single-run detail + 2-way compare. Experiment trigger UI is v1.2 (Phase 7.1); sweep heatmap is v1.3 (Phase 7.2). See ROADMAP.md.
