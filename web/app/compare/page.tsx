import Link from "next/link";
import { getManifest, getRun } from "@/lib/api";
import NavChart from "@/components/NavChart";
import MetricsTable from "@/components/MetricsTable";
import AllocationTable from "@/components/AllocationTable";
import type { BacktestManifest, RunDetail, SignalManifest } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string }>;
}) {
  const { ids } = await searchParams;
  const idList = (ids ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (idList.length !== 2) {
    return (
      <div className="panel-pad text-sm leading-6">
        <p className="mb-2 font-medium">对比功能需要正好两条实验记录。</p>
        <p>
          当前传入：<code>{ids ?? "(空)"}</code>。请回到
          {" "}
          <Link href="/" className="text-link">
            实验列表
          </Link>
          {" "}
          重新勾选两条。
        </p>
      </div>
    );
  }

  const [a, b] = await Promise.all(idList.map(loadRun));

  const navSeries = [a, b]
    .filter((r): r is LoadedRun & { kind: "broad_index_backtest" } =>
      r.kind === "broad_index_backtest"
    )
    .map((r) => ({
      label: r.run.label,
      points: (r.manifest as BacktestManifest).curve ?? [],
    }));

  const metricsColumns = [a, b]
    .filter((r): r is LoadedRun & { kind: "broad_index_backtest" } =>
      r.kind === "broad_index_backtest"
    )
    .map((r) => ({
      label: r.run.label,
      metrics: (r.manifest as BacktestManifest).metrics,
    }));

  const allocationColumns = [a, b].map((r) => ({
    label: r.run.label,
    weights: extractAllocationWeights(r),
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-baseline">
        <Link href="/" className="text-link inline-flex min-h-11 items-center text-sm sm:min-h-10">
          ← 返回列表
        </Link>
        <h1 className="text-xl font-semibold text-slate-950">策略对比</h1>
        <span className="break-words text-sm text-slate-500">
          {a.run.label} vs {b.run.label}
        </span>
      </div>

      {navSeries.length === 2 ? (
        <section>
          <h2 className="section-title">净值曲线（叠加）</h2>
          <NavChart series={navSeries} />
        </section>
      ) : (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm leading-6 text-yellow-800">
          叠加净值曲线需要两条均为回测的实验。当前所选记录中存在非回测，仅展示持仓对比。
        </div>
      )}

      {metricsColumns.length === 2 && (
        <section>
          <h2 className="section-title">指标对比</h2>
          <MetricsTable columns={metricsColumns} />
        </section>
      )}

      <section>
        <h2 className="section-title">持仓差异</h2>
        <AllocationTable columns={allocationColumns} />
      </section>
    </div>
  );
}

type LoadedRun = {
  run: RunDetail;
  kind: RunDetail["kind"];
  manifest: BacktestManifest | SignalManifest | Record<string, unknown>;
};

async function loadRun(id: string): Promise<LoadedRun> {
  const [run, manifest] = await Promise.all([getRun(id), getManifest(id)]);
  return { run, kind: run.kind, manifest };
}

function extractAllocationWeights(loaded: LoadedRun): Record<string, number> {
  if (loaded.kind === "broad_index_signal") {
    const m = loaded.manifest as SignalManifest;
    return Object.fromEntries(m.target_plan.holdings.map((h) => [h.etf_code, h.weight]));
  }
  if (loaded.kind === "broad_index_backtest") {
    const m = loaded.manifest as BacktestManifest;
    const last = m.rebalances?.[m.rebalances.length - 1];
    return last?.realized_weights_after ?? {};
  }
  return {};
}
