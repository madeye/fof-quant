"use client";

import ReactECharts from "echarts-for-react";
import type { CurvePoint } from "@/lib/types";

export default function DrawdownChart({ points }: { points: CurvePoint[] }) {
  const option = {
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: { type: "category", data: points.map((p) => p.trade_date), boundaryGap: false },
    yAxis: {
      type: "value",
      name: "回撤",
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
    },
    series: [
      {
        name: "回撤",
        type: "line",
        symbol: "none",
        areaStyle: { color: "rgba(220, 38, 38, 0.15)" },
        lineStyle: { color: "#dc2626" },
        data: points.map((p) => p.drawdown),
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 200 }} notMerge />;
}
