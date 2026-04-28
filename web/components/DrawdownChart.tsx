"use client";

import ReactECharts from "echarts-for-react";
import type { CurvePoint } from "@/lib/types";

export type DrawdownSeries = {
  label: string;
  points: Pick<CurvePoint, "trade_date" | "drawdown">[];
};

const PALETTE = [
  { line: "#dc2626", area: "rgba(220, 38, 38, 0.15)" }, // 策略 — 红
  { line: "#2563eb", area: "rgba(37, 99, 235, 0.10)" }, // 基准 — 蓝
  { line: "#16a34a", area: "rgba(22, 163, 74, 0.10)" },
];

/**
 * 回撤曲线图。支持多条 series 叠加，第二条默认呈现为基准。
 * 接受 legacy 单序列调用（直接传入 points），也接受多序列调用（传入 series[]）。
 */
export default function DrawdownChart({
  points,
  series,
}: {
  points?: Pick<CurvePoint, "trade_date" | "drawdown">[];
  series?: DrawdownSeries[];
}) {
  const resolved: DrawdownSeries[] =
    series && series.length > 0
      ? series
      : points
        ? [{ label: "回撤", points }]
        : [];
  const allDates = Array.from(
    new Set(resolved.flatMap((s) => s.points.map((p) => p.trade_date)))
  ).sort();
  const option = {
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number | null) =>
        v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(2)}%`,
    },
    legend:
      resolved.length > 1
        ? {
            data: resolved.map((s) => s.label),
            type: "scroll",
            top: 0,
            textStyle: { color: "#475569", fontSize: 12 },
          }
        : undefined,
    grid: {
      left: 42,
      right: 18,
      top: resolved.length > 1 ? 48 : 32,
      bottom: 34,
      containLabel: true,
    },
    xAxis: { type: "category", data: allDates, boundaryGap: false },
    yAxis: {
      type: "value",
      name: "回撤",
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
    },
    series: resolved.map((s, idx) => {
      const palette = PALETTE[idx] ?? PALETTE[PALETTE.length - 1];
      return {
        name: s.label,
        type: "line",
        symbol: "none",
        areaStyle: idx === 0 ? { color: palette.area } : undefined,
        lineStyle: { color: palette.line },
        data: alignDrawdown(s.points, allDates),
      };
    }),
  };
  return (
    <div className="panel p-2 sm:p-3">
      <ReactECharts
        className="w-full"
        option={option}
        style={{ height: "clamp(220px, 34vw, 280px)" }}
        notMerge
      />
    </div>
  );
}

function alignDrawdown(
  points: Pick<CurvePoint, "trade_date" | "drawdown">[],
  dates: string[]
): (number | null)[] {
  const map = new Map(points.map((p) => [p.trade_date, p.drawdown]));
  return dates.map((d) => {
    const v = map.get(d);
    return v == null || !Number.isFinite(v) ? null : v;
  });
}
