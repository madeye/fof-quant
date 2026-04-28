import { formatPct, formatRatio } from "@/lib/format";
import { metricLabel } from "@/lib/labels";

const PERCENT_KEYS = new Set([
  "total_return",
  "annualized_return",
  "volatility",
  "max_drawdown",
  "win_rate",
  "tracking_error",
]);

const ORDER = [
  "total_return",
  "annualized_return",
  "volatility",
  "sharpe",
  "max_drawdown",
  "calmar",
  "win_rate",
  "tracking_error",
];

export type MetricsColumn = {
  label: string;
  metrics: Record<string, number> | null;
};

export default function MetricsTable({ columns }: { columns: MetricsColumn[] }) {
  const showDelta = columns.length === 2;
  const keys = ORDER.filter((k) =>
    columns.some((c) => c.metrics && k in c.metrics)
  );
  return (
    <div className="table-wrap">
      <table className="data-table min-w-[520px]">
        <thead>
          <tr>
            <th>指标</th>
            {columns.map((c) => (
              <th key={c.label} className="max-w-48 text-right">
                {c.label}
              </th>
            ))}
            {showDelta && (
              <th className="text-right">差值（B − A）</th>
            )}
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr key={key}>
              <td className="px-3 py-2">{metricLabel(key)}</td>
              {columns.map((c) => (
                <td key={`${c.label}-${key}`} className="px-3 py-2 text-right tabular-nums">
                  {formatMetric(key, c.metrics?.[key])}
                </td>
              ))}
              {showDelta && (
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatDelta(
                    key,
                    columns[0].metrics?.[key],
                    columns[1].metrics?.[key]
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatMetric(key: string, value: number | undefined): string {
  if (value === undefined) return "—";
  return PERCENT_KEYS.has(key) ? formatPct(value) : formatRatio(value);
}

function formatDelta(
  key: string,
  a: number | undefined,
  b: number | undefined
): string {
  if (a === undefined || b === undefined) return "—";
  const diff = b - a;
  return PERCENT_KEYS.has(key)
    ? `${diff >= 0 ? "+" : ""}${formatPct(diff)}`
    : `${diff >= 0 ? "+" : ""}${formatRatio(diff)}`;
}
