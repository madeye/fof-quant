"use client";

import ReactECharts from "echarts-for-react";
import type { CurvePoint } from "@/lib/types";

export type NavSeries = {
  label: string;
  points: Pick<CurvePoint, "trade_date" | "nav">[];
};

/**
 * 净值曲线图。所有 series 都会以各自第一个有限值归一化到 1.0，
 * 这样不同量级（如以 CNY 计价的策略 NAV 与已归一化的基准）可以
 * 在同一坐标系下比较。
 */
export default function NavChart({ series }: { series: NavSeries[] }) {
  const allDates = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.trade_date)))
  ).sort();
  const option = {
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number | null) =>
        v == null || !Number.isFinite(v) ? "—" : v.toFixed(4),
    },
    legend: {
      data: series.map((s) => s.label),
      type: "scroll",
      top: 0,
      textStyle: { color: "#475569", fontSize: 12 },
    },
    grid: { left: 42, right: 18, top: 48, bottom: 38, containLabel: true },
    xAxis: { type: "category", data: allDates, boundaryGap: false },
    yAxis: {
      type: "value",
      scale: true,
      name: "净值",
      axisLabel: { formatter: (v: number) => v.toFixed(2) },
    },
    series: series.map((s) => ({
      name: s.label,
      type: "line",
      smooth: true,
      symbol: "none",
      data: alignAndNormalize(s.points, allDates),
    })),
  };
  return (
    <div className="panel p-2 sm:p-3">
      <ReactECharts
        className="w-full"
        option={option}
        style={{ height: "clamp(280px, 44vw, 360px)" }}
        notMerge
      />
    </div>
  );
}

function alignAndNormalize(
  points: Pick<CurvePoint, "trade_date" | "nav">[],
  dates: string[]
): (number | null)[] {
  const map = new Map(points.map((p) => [p.trade_date, p.nav]));
  const base = points.find((p) => Number.isFinite(p.nav) && p.nav !== 0)?.nav;
  if (base === undefined) return dates.map(() => null);
  return dates.map((d) => {
    const v = map.get(d);
    return v == null || !Number.isFinite(v) ? null : v / base;
  });
}
