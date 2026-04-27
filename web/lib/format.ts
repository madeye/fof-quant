// 中文风格数字格式化工具，与现有 HTML 报告保持一致。

const YI = 100_000_000;
const WAN = 10_000;

export function formatPct(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatRatio(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function formatYi(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value / YI).toFixed(2)} 亿元`;
}

export function formatCny(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `¥${value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

/**
 * 自动按量级选择 亿/万/元 单位，符合中文金融报告习惯。
 */
export function formatMoney(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= YI) return `${sign}${(abs / YI).toFixed(2)} 亿元`;
  if (abs >= WAN) return `${sign}${(abs / WAN).toFixed(2)} 万元`;
  return `${sign}${abs.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 元`;
}

/**
 * 带正负号的金额变化（用于 Δ 列）。
 */
export function formatMoneyDelta(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return formatMoney(0);
  const formatted = formatMoney(value);
  return value > 0 && !formatted.startsWith("+") ? `+${formatted}` : formatted;
}

export function formatInt(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length === 10 ? value : value.slice(0, 10);
}
