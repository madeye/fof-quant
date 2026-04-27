export type RunStatus = "queued" | "running" | "completed" | "failed" | string;

export type RunKind =
  | "broad_index_signal"
  | "broad_index_backtest"
  | "offline_pipeline"
  | "sweep";

export type RunSummary = {
  id: string;
  kind: RunKind;
  label: string;
  as_of_date: string | null;
  status: RunStatus;
  created_at: string;
  output_dir: string;
  error?: string | null;
};

export type RunDetail = RunSummary & {
  manifest_path: string;
  report_html_path: string | null;
  metrics: Record<string, number> | null;
  benchmark_metrics: Record<string, number> | null;
};

export type CurvePoint = {
  trade_date: string;
  nav: number;
  daily_return: number;
  drawdown: number;
};

export type BacktestManifest = {
  as_of_start: string | null;
  as_of_end: string | null;
  metrics: Record<string, number>;
  benchmark_metrics: Record<string, number> | null;
  curve: CurvePoint[];
  rebalances: Array<{
    trade_date: string;
    nav_before: number;
    turnover_pct: number;
    cost_cny: number;
    triggered_codes: string[];
    target_weights: Record<string, number>;
    realized_weights_after: Record<string, number>;
  }>;
};

export type SignalManifest = {
  as_of: string;
  total_aum_cny: number;
  sleeve_weights: Record<string, number>;
  target_plan: {
    holdings: Array<{ etf_code: string; weight: number; score: number; reason: string }>;
    cash_weight: number;
    constraint_checks: Record<string, unknown>;
  };
  rebalance_lines: Array<{
    ts_code: string;
    sleeve: string;
    target_weight: number;
    current_weight: number;
    drift_pp: number;
    drift_rel_pct: number;
    action: string;
    target_notional_cny: number;
    delta_notional_cny: number;
    last_price: number;
    delta_shares_lot100: number;
  }>;
  trade_count: number;
};

export type SweepRow = {
  scheme: string;
  band_pp: number;
  final_nav: number;
  cagr: number;
  vol: number;
  sharpe: number;
  max_drawdown: number;
  calmar: number;
  tracking_error: number;
  rebalances: number;
  avg_turnover_pct: number;
  total_cost_cny: number;
};

export type SweepManifest = {
  start_date: string;
  end_date: string;
  schemes: string[];
  bands_pp: number[];
  rows: SweepRow[];
  benchmark: Record<string, number> | null;
};

export type Manifest =
  | BacktestManifest
  | SignalManifest
  | SweepManifest
  | Record<string, unknown>;

export type BroadIndexBacktestParams = {
  start_date: string;
  end_date: string;
  initial_cash: number;
  sleeve_weights?: Record<string, number> | null;
  cash_buffer: number;
  max_weight: number;
  abs_band_pp: number;
  rel_band_pct: number;
  transaction_cost_bps: number;
  slippage_bps: number;
  benchmark_label: string;
  label?: string | null;
};

export type CreateRunPayload = {
  kind: "broad_index_backtest";
  params: BroadIndexBacktestParams;
};
