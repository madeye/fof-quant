// 中文风格数字格式化工具，与现有 HTML 报告保持一致。

export function formatPct(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatRatio(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function formatYi(value: number): string {
  // ¥ in 亿元
  if (!Number.isFinite(value)) return "—";
  const yi = value / 100_000_000;
  return `${yi.toFixed(2)} 亿`;
}

export function formatCny(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `¥${value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length === 10 ? value : value.slice(0, 10);
}
