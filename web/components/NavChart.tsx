"use client";

import ReactECharts from "echarts-for-react";
import type { CurvePoint } from "@/lib/types";

export type NavSeries = {
  label: string;
  points: Pick<CurvePoint, "trade_date" | "nav">[];
};

export default function NavChart({ series }: { series: NavSeries[] }) {
  const allDates = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.trade_date)))
  ).sort();
  const option = {
    tooltip: { trigger: "axis" },
    legend: { data: series.map((s) => s.label) },
    grid: { left: 50, right: 30, top: 40, bottom: 40 },
    xAxis: { type: "category", data: allDates, boundaryGap: false },
    yAxis: { type: "value", scale: true, name: "NAV" },
    series: series.map((s) => ({
      name: s.label,
      type: "line",
      smooth: true,
      symbol: "none",
      data: alignSeries(s.points, allDates),
    })),
  };
  return <ReactECharts option={option} style={{ height: 360 }} notMerge />;
}

function alignSeries(
  points: Pick<CurvePoint, "trade_date" | "nav">[],
  dates: string[]
): (number | null)[] {
  const map = new Map(points.map((p) => [p.trade_date, p.nav]));
  return dates.map((d) => map.get(d) ?? null);
}
