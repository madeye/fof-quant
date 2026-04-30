"use client";

import { useEffect, useState } from "react";
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
  const isDark = useDarkMode();
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const mutedColor = isDark ? "#64748b" : "#94a3b8";
  const splitLineColor = isDark ? "#1e293b" : "#e2e8f0";
  const tooltipBackground = isDark ? "rgba(15, 23, 42, 0.96)" : "rgba(255, 255, 255, 0.96)";
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
    backgroundColor: "transparent",
    textStyle: { color: textColor },
    tooltip: {
      trigger: "axis",
      backgroundColor: tooltipBackground,
      borderColor: splitLineColor,
      textStyle: { color: textColor },
      valueFormatter: (v: number | null) =>
        v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(2)}%`,
    },
    legend:
      resolved.length > 1
        ? {
            data: resolved.map((s) => s.label),
            type: "scroll",
            top: 0,
            textStyle: { color: textColor, fontSize: 12 },
          }
        : undefined,
    grid: {
      left: 42,
      right: 18,
      top: resolved.length > 1 ? 48 : 32,
      bottom: 34,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: allDates,
      boundaryGap: false,
      axisLabel: { color: mutedColor },
      axisLine: { lineStyle: { color: splitLineColor } },
      axisTick: { lineStyle: { color: splitLineColor } },
    },
    yAxis: {
      type: "value",
      name: "回撤",
      nameTextStyle: { color: textColor },
      axisLabel: { color: mutedColor, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { color: splitLineColor } },
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

function useDarkMode(): boolean {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const update = () => setIsDark(root.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return isDark;
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
