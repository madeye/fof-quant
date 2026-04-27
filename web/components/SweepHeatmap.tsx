"use client";

import ReactECharts from "echarts-for-react";
import type { SweepRow } from "@/lib/types";

type MetricKey =
  | "sharpe"
  | "cagr"
  | "max_drawdown"
  | "calmar"
  | "tracking_error"
  | "avg_turnover_pct";

const PERCENT_METRICS: ReadonlySet<MetricKey> = new Set([
  "cagr",
  "max_drawdown",
  "tracking_error",
  "avg_turnover_pct",
]);

export type SweepHeatmapProps = {
  schemes: string[];
  bands: number[];
  rows: SweepRow[];
  metric: MetricKey;
};

export default function SweepHeatmap({
  schemes,
  bands,
  rows,
  metric,
}: SweepHeatmapProps) {
  const cells: [number, number, number][] = [];
  let min = Infinity;
  let max = -Infinity;
  rows.forEach((row) => {
    const x = bands.indexOf(row.band_pp);
    const y = schemes.indexOf(row.scheme);
    if (x === -1 || y === -1) return;
    const raw = row[metric];
    if (!Number.isFinite(raw)) return;
    const value = PERCENT_METRICS.has(metric) ? raw * 100 : raw;
    cells.push([x, y, value]);
    if (value < min) min = value;
    if (value > max) max = value;
  });
  const isDescending = metric === "max_drawdown" || metric === "tracking_error";
  const inMin = Number.isFinite(min) ? min : 0;
  const inMax = Number.isFinite(max) ? max : 1;

  const option = {
    tooltip: {
      formatter: (p: { data: [number, number, number] }) => {
        const [x, y, v] = p.data;
        const suffix = PERCENT_METRICS.has(metric) ? "%" : "";
        return `${schemes[y]} · band ${bands[x]}<br/>${metric}: ${v.toFixed(
          2
        )}${suffix}`;
      },
    },
    grid: { left: 140, right: 20, top: 30, bottom: 60 },
    xAxis: {
      type: "category",
      data: bands.map((b) => `${b}pp`),
      name: "Band",
      splitArea: { show: true },
    },
    yAxis: {
      type: "category",
      data: schemes,
      splitArea: { show: true },
    },
    visualMap: {
      min: inMin,
      max: inMax,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 10,
      inRange: {
        color: isDescending
          ? ["#15803d", "#fde68a", "#dc2626"]
          : ["#dc2626", "#fde68a", "#15803d"],
      },
    },
    series: [
      {
        type: "heatmap",
        data: cells,
        label: {
          show: true,
          formatter: (p: { data: [number, number, number] }) => {
            const v = p.data[2];
            const suffix = PERCENT_METRICS.has(metric) ? "%" : "";
            return `${v.toFixed(2)}${suffix}`;
          },
          fontSize: 11,
        },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 60 + schemes.length * 36 }} notMerge />;
}
