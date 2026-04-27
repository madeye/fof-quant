import Link from "next/link";
import { getManifest, getRun, reportUrl } from "@/lib/api";
import NavChart from "@/components/NavChart";
import DrawdownChart from "@/components/DrawdownChart";
import MetricsTable from "@/components/MetricsTable";
import AllocationTable from "@/components/AllocationTable";
import type { BacktestManifest, SignalManifest } from "@/lib/types";
import { formatCny, formatPct, formatYi } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [run, manifest] = await Promise.all([getRun(id), getManifest(id)]);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-3">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Runs
        </Link>
        <h1 className="text-xl font-semibold">{run.label}</h1>
        <span className="text-sm text-slate-500">{run.kind}</span>
        {run.report_html_path && (
          <a
            href={reportUrl(id)}
            target="_blank"
            rel="noreferrer"
            className="ml-auto rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            Open original HTML report ↗
          </a>
        )}
      </div>

      {run.kind === "broad_index_backtest" ? (
        <BacktestView run={run.label} manifest={manifest as BacktestManifest} />
      ) : run.kind === "broad_index_signal" ? (
        <SignalView manifest={manifest as SignalManifest} />
      ) : (
        <pre className="overflow-auto rounded border bg-white p-3 text-xs">
          {JSON.stringify(manifest, null, 2)}
        </pre>
      )}
    </div>
  );
}

function BacktestView({ run, manifest }: { run: string; manifest: BacktestManifest }) {
  const curve = manifest.curve ?? [];
  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">NAV</h2>
        <NavChart series={[{ label: run, points: curve }]} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">Drawdown</h2>
        <DrawdownChart points={curve} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">Metrics</h2>
        <MetricsTable
          columns={[
            { label: "Strategy", metrics: manifest.metrics },
            ...(manifest.benchmark_metrics
              ? [{ label: "Benchmark", metrics: manifest.benchmark_metrics }]
              : []),
          ]}
        />
      </section>
    </div>
  );
}

function SignalView({ manifest }: { manifest: SignalManifest }) {
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-3 gap-3">
        <Card label="As of" value={manifest.as_of} />
        <Card label="Total AUM" value={formatYi(manifest.total_aum_cny)} />
        <Card label="Trade count" value={String(manifest.trade_count)} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">Target Allocation</h2>
        <AllocationTable
          columns={[
            {
              label: "Target",
              weights: Object.fromEntries(
                manifest.target_plan.holdings.map((h) => [h.etf_code, h.weight])
              ),
            },
          ]}
        />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">Rebalance Lines</h2>
        <div className="overflow-auto rounded border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Sleeve</th>
                <th className="px-3 py-2 text-left">Code</th>
                <th className="px-3 py-2 text-right">Target</th>
                <th className="px-3 py-2 text-right">Current</th>
                <th className="px-3 py-2 text-right">Drift (pp)</th>
                <th className="px-3 py-2 text-left">Action</th>
                <th className="px-3 py-2 text-right">Δ Notional</th>
                <th className="px-3 py-2 text-right">Δ Shares</th>
              </tr>
            </thead>
            <tbody>
              {manifest.rebalance_lines.map((line) => (
                <tr key={line.ts_code} className="border-t">
                  <td className="px-3 py-2">{line.sleeve}</td>
                  <td className="px-3 py-2 font-mono text-xs">{line.ts_code}</td>
                  <td className="px-3 py-2 text-right">{formatPct(line.target_weight)}</td>
                  <td className="px-3 py-2 text-right">{formatPct(line.current_weight)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {line.drift_pp.toFixed(2)}
                  </td>
                  <td className="px-3 py-2">{line.action}</td>
                  <td className="px-3 py-2 text-right">{formatCny(line.delta_notional_cny)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {line.delta_shares_lot100}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
