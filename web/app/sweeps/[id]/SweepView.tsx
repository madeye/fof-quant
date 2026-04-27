"use client";

import { useState } from "react";
import SweepHeatmap from "@/components/SweepHeatmap";
import type { SweepManifest } from "@/lib/types";

const METRICS = [
  { key: "sharpe", label: "夏普比率" },
  { key: "cagr", label: "年化收益" },
  { key: "max_drawdown", label: "最大回撤" },
  { key: "calmar", label: "卡玛比率" },
  { key: "tracking_error", label: "跟踪误差" },
  { key: "avg_turnover_pct", label: "平均换手率" },
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
          <span className="text-sm text-slate-700">指标：</span>
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
          按「{METRICS.find((m) => m.key === metric)?.label ?? metric}」排名前 10
        </h2>
        <div className="overflow-auto rounded border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">排名</th>
                <th className="px-3 py-2 text-left">方案</th>
                <th className="px-3 py-2 text-right">区间</th>
                <th className="px-3 py-2 text-right">年化收益</th>
                <th className="px-3 py-2 text-right">年化波动</th>
                <th className="px-3 py-2 text-right">夏普</th>
                <th className="px-3 py-2 text-right">最大回撤</th>
                <th className="px-3 py-2 text-right">卡玛</th>
                <th className="px-3 py-2 text-right">换手率</th>
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
          <span className="font-medium">基准：</span>{" "}
          年化 {(manifest.benchmark.annualized_return * 100).toFixed(2)}% · 波动{" "}
          {(manifest.benchmark.volatility * 100).toFixed(2)}% · 夏普{" "}
          {manifest.benchmark.sharpe.toFixed(2)} · 最大回撤{" "}
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
