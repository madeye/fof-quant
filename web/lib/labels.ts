import type { RunKind } from "./types";

export const KIND_LABELS: Record<RunKind, string> = {
  broad_index_signal: "宽基信号",
  broad_index_backtest: "宽基回测",
  offline_pipeline: "离线流水线",
  sweep: "参数扫描",
};

export function kindLabel(kind: RunKind | string): string {
  return (KIND_LABELS as Record<string, string>)[kind] ?? kind;
}

export const METRIC_LABELS: Record<string, string> = {
  total_return: "总收益",
  annualized_return: "年化收益",
  volatility: "年化波动",
  sharpe: "夏普比率",
  max_drawdown: "最大回撤",
  calmar: "卡玛比率",
  win_rate: "胜率",
  tracking_error: "跟踪误差",
};

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key;
}
