export type RunSummary = {
  id: string;
  kind: "broad_index_signal" | "broad_index_backtest" | "offline_pipeline";
  label: string;
  as_of_date: string | null;
  status: string;
  created_at: string;
  output_dir: string;
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

export type Manifest = BacktestManifest | SignalManifest | Record<string, unknown>;
