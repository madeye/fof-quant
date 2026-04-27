"use client";

import { useState } from "react";
import SweepHeatmap from "@/components/SweepHeatmap";
import type { SweepManifest } from "@/lib/types";

const METRICS = [
  { key: "sharpe", label: "Sharpe" },
  { key: "cagr", label: "CAGR" },
  { key: "max_drawdown", label: "Max Drawdown" },
  { key: "calmar", label: "Calmar" },
  { key: "tracking_error", label: "Tracking Error" },
  { key: "avg_turnover_pct", label: "Avg Turnover" },
] as const;

type MetricKey = (typeof METRICS)[number]["key"];

export default function SweepView({ manifest }: { manifest: SweepManifest }) {
  const [metric, setMetric] = useState<MetricKey>("sharpe");
  const sortedRows = [...manifest.rows].sort(
    (a, b) =>
      compareMetric(b, metric) - compareMetric(a, metric) ||
      a.scheme.localeCompare(b.scheme) ||
      a.band_pp - b.band_pp
  );
  const topRows = sortedRows.slice(0, 10);
  return (
    <div className="space-y-6">
      <section>
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm text-slate-700">Metric:</span>
          <div className="flex flex-wrap gap-1">
            {METRICS.map((m) => (
              <button
                key={m.key}
                onClick={() => setMetric(m.key)}
                className={
                  "rounded border px-2 py-1 text-xs " +
                  (metric === m.key
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-slate-700 hover:bg-slate-100")
                }
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <SweepHeatmap
          schemes={manifest.schemes}
          bands={manifest.bands_pp}
          rows={manifest.rows}
          metric={metric}
        />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">
          Top 10 by {METRICS.find((m) => m.key === metric)?.label ?? metric}
        </h2>
        <div className="overflow-auto rounded border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Rank</th>
                <th className="px-3 py-2 text-left">Scheme</th>
                <th className="px-3 py-2 text-right">Band</th>
                <th className="px-3 py-2 text-right">CAGR</th>
                <th className="px-3 py-2 text-right">Vol</th>
                <th className="px-3 py-2 text-right">Sharpe</th>
                <th className="px-3 py-2 text-right">Max DD</th>
                <th className="px-3 py-2 text-right">Calmar</th>
                <th className="px-3 py-2 text-right">Turnover</th>
              </tr>
            </thead>
            <tbody>
              {topRows.map((row, idx) => (
                <tr key={`${row.scheme}-${row.band_pp}`} className="border-t">
                  <td className="px-3 py-2">{idx + 1}</td>
                  <td className="px-3 py-2">{row.scheme}</td>
                  <td className="px-3 py-2 text-right">{row.band_pp.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(row.cagr * 100).toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(row.vol * 100).toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {row.sharpe.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(row.max_drawdown * 100).toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {row.calmar.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(row.avg_turnover_pct * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {manifest.benchmark && (
        <section className="rounded border bg-white p-3 text-sm text-slate-700">
          <span className="font-medium">Benchmark:</span>{" "}
          CAGR {(manifest.benchmark.annualized_return * 100).toFixed(2)}%, Vol{" "}
          {(manifest.benchmark.volatility * 100).toFixed(2)}%, Sharpe{" "}
          {manifest.benchmark.sharpe.toFixed(2)}, Max DD{" "}
          {(manifest.benchmark.max_drawdown * 100).toFixed(2)}%
        </section>
      )}
    </div>
  );
}

function compareMetric(row: SweepManifest["rows"][number], key: MetricKey): number {
  const v = row[key];
  return Number.isFinite(v) ? v : -Infinity;
}
