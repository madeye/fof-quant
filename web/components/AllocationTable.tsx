import { formatPct } from "@/lib/format";

export type AllocationColumn = {
  label: string;
  weights: Record<string, number>;
};

export default function AllocationTable({ columns }: { columns: AllocationColumn[] }) {
  const codes = Array.from(
    new Set(columns.flatMap((c) => Object.keys(c.weights)))
  ).sort();
  const showDelta = columns.length === 2;
  return (
    <div className="overflow-auto rounded border bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100">
          <tr>
            <th className="px-3 py-2 text-left font-medium">ETF</th>
            {columns.map((c) => (
              <th key={c.label} className="px-3 py-2 text-right font-medium">
                {c.label}
              </th>
            ))}
            {showDelta && (
              <th className="px-3 py-2 text-right font-medium">Δ</th>
            )}
          </tr>
        </thead>
        <tbody>
          {codes.map((code) => (
            <tr key={code} className="border-t">
              <td className="px-3 py-2 font-mono text-xs">{code}</td>
              {columns.map((c) => (
                <td key={`${c.label}-${code}`} className="px-3 py-2 text-right tabular-nums">
                  {code in c.weights ? formatPct(c.weights[code]) : "—"}
                </td>
              ))}
              {showDelta && (
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatDelta(columns[0].weights[code], columns[1].weights[code])}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDelta(a: number | undefined, b: number | undefined): string {
  const av = a ?? 0;
  const bv = b ?? 0;
  const diff = bv - av;
  return `${diff >= 0 ? "+" : ""}${formatPct(diff)}`;
}
