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
      <div className="rounded border bg-white p-4 text-sm">
        <p className="mb-2 font-medium">Compare needs exactly two run ids.</p>
        <p>
          Got: <code>{ids ?? "(none)"}</code>. Go back to the{" "}
          <Link href="/" className="text-blue-600 hover:underline">
            run list
          </Link>{" "}
          and select two.
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
      <div className="flex items-baseline gap-3">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Runs
        </Link>
        <h1 className="text-xl font-semibold">Compare</h1>
        <span className="text-sm text-slate-500">
          {a.run.label} vs {b.run.label}
        </span>
      </div>

      {navSeries.length === 2 ? (
        <section>
          <h2 className="text-sm font-medium mb-2 text-slate-700">NAV (overlay)</h2>
          <NavChart series={navSeries} />
        </section>
      ) : (
        <div className="rounded border bg-yellow-50 p-3 text-sm text-yellow-800">
          NAV overlay needs two backtest runs. One or both selected runs are not
          backtests; comparing allocations only.
        </div>
      )}

      {metricsColumns.length === 2 && (
        <section>
          <h2 className="text-sm font-medium mb-2 text-slate-700">Metrics (side by side)</h2>
          <MetricsTable columns={metricsColumns} />
        </section>
      )}

      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">Allocation diff</h2>
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
