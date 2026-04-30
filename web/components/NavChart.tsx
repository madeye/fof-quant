"use client";

import { useEffect, useState } from "react";
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
  const isDark = useDarkMode();
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const mutedColor = isDark ? "#64748b" : "#94a3b8";
  const splitLineColor = isDark ? "#1e293b" : "#e2e8f0";
  const tooltipBackground = isDark ? "rgba(15, 23, 42, 0.96)" : "rgba(255, 255, 255, 0.96)";
  const allDates = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.trade_date)))
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
        v == null || !Number.isFinite(v) ? "—" : v.toFixed(4),
    },
    legend: {
      data: series.map((s) => s.label),
      type: "scroll",
      top: 0,
      textStyle: { color: textColor, fontSize: 12 },
    },
    grid: { left: 42, right: 18, top: 48, bottom: 38, containLabel: true },
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
      scale: true,
      name: "净值",
      nameTextStyle: { color: textColor },
      axisLabel: { color: mutedColor, formatter: (v: number) => v.toFixed(2) },
      axisLine: { lineStyle: { color: splitLineColor } },
      splitLine: { lineStyle: { color: splitLineColor } },
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
