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
    <div className="overflow-auto rounded border bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100">
          <tr>
            <th className="px-3 py-2 text-left font-medium">指标</th>
            {columns.map((c) => (
              <th key={c.label} className="px-3 py-2 text-right font-medium">
                {c.label}
              </th>
            ))}
            {showDelta && (
              <th className="px-3 py-2 text-right font-medium">差值（B − A）</th>
            )}
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr key={key} className="border-t">
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
