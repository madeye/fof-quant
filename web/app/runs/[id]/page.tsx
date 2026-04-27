import Link from "next/link";
import { getManifest, getRun, reportUrl } from "@/lib/api";
import NavChart from "@/components/NavChart";
import DrawdownChart from "@/components/DrawdownChart";
import MetricsTable from "@/components/MetricsTable";
import AllocationTable from "@/components/AllocationTable";
import AutoRefresh from "@/components/AutoRefresh";
import StatusBadge from "@/components/StatusBadge";
import type { BacktestManifest, RunDetail, SignalManifest } from "@/lib/types";
import { formatMoneyDelta, formatPct, formatYi } from "@/lib/format";
import { kindLabel } from "@/lib/labels";

export const dynamic = "force-dynamic";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await getRun(id);
  const inProgress = run.status === "queued" || run.status === "running";
  const failed = run.status === "failed";

  let manifest: unknown = null;
  if (!inProgress && !failed) {
    try {
      manifest = await getManifest(id);
    } catch (err) {
      // Manifest is missing on disk — render the run shell with a warning.
      manifest = { _error: err instanceof Error ? err.message : String(err) };
    }
  }

  return (
    <div className="space-y-6">
      {inProgress && <AutoRefresh intervalMs={2000} />}
      <Header run={run} runId={id} />
      {inProgress ? (
        <ProgressPanel status={run.status} />
      ) : failed ? (
        <ErrorPanel error={run.error ?? "(no error message recorded)"} />
      ) : run.kind === "broad_index_backtest" ? (
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

function Header({ run, runId }: { run: RunDetail; runId: string }) {
  return (
    <div className="flex items-baseline gap-3 flex-wrap">
      <Link href="/" className="text-sm text-blue-600 hover:underline">
        ← 返回列表
      </Link>
      <h1 className="text-xl font-semibold">{run.label}</h1>
      <span className="text-sm text-slate-500">{kindLabel(run.kind)}</span>
      <StatusBadge status={run.status} />
      {run.report_html_path && (
        <a
          href={reportUrl(runId)}
          target="_blank"
          rel="noreferrer"
          className="ml-auto rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
        >
          打开原始 HTML 报告 ↗
        </a>
      )}
    </div>
  );
}

function ProgressPanel({ status }: { status: string }) {
  const label = status === "queued" ? "排队中" : status === "running" ? "运行中" : status;
  return (
    <div className="rounded border bg-white p-6 text-sm text-slate-700">
      <div className="font-medium mb-1">实验当前状态：{label}…</div>
      <div className="text-slate-500">
        本页每 2 秒自动刷新一次，运行完成后会自动加载结果。
      </div>
    </div>
  );
}

function ErrorPanel({ error }: { error: string }) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <div className="font-medium mb-1">实验运行失败</div>
      <pre className="whitespace-pre-wrap text-xs">{error}</pre>
    </div>
  );
}

function BacktestView({ run, manifest }: { run: string; manifest: BacktestManifest }) {
  const curve = manifest.curve ?? [];
  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">净值曲线</h2>
        <NavChart series={[{ label: run, points: curve }]} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">回撤曲线</h2>
        <DrawdownChart points={curve} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">绩效指标</h2>
        <MetricsTable
          columns={[
            { label: "策略", metrics: manifest.metrics },
            ...(manifest.benchmark_metrics
              ? [{ label: "基准", metrics: manifest.benchmark_metrics }]
              : []),
          ]}
        />
      </section>
    </div>
  );
}

const ACTION_LABELS: Record<string, string> = {
  initial: "建仓",
  buy: "加仓",
  sell: "减仓",
  hold: "持有",
  open: "开仓",
  close: "清仓",
};

function SignalView({ manifest }: { manifest: SignalManifest }) {
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-3 gap-3">
        <Card label="截至日期" value={manifest.as_of} />
        <Card label="总规模" value={formatYi(manifest.total_aum_cny)} />
        <Card label="本次交易笔数" value={String(manifest.trade_count)} />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">目标持仓</h2>
        <AllocationTable
          columns={[
            {
              label: "目标权重",
              weights: Object.fromEntries(
                manifest.target_plan.holdings.map((h) => [h.etf_code, h.weight])
              ),
            },
          ]}
        />
      </section>
      <section>
        <h2 className="text-sm font-medium mb-2 text-slate-700">再平衡明细</h2>
        <div className="overflow-auto rounded border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">板块</th>
                <th className="px-3 py-2 text-left">代码</th>
                <th className="px-3 py-2 text-right">目标权重</th>
                <th className="px-3 py-2 text-right">当前权重</th>
                <th className="px-3 py-2 text-right">偏离（pp）</th>
                <th className="px-3 py-2 text-left">操作</th>
                <th className="px-3 py-2 text-right">交易金额</th>
                <th className="px-3 py-2 text-right">交易股数</th>
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
                  <td className="px-3 py-2">{ACTION_LABELS[line.action] ?? line.action}</td>
                  <td className="px-3 py-2 text-right">
                    {formatMoneyDelta(line.delta_notional_cny)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {line.delta_shares_lot100.toLocaleString("zh-CN")}
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
