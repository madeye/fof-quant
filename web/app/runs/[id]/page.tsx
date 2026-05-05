import Link from "next/link";
import { getManifest, getRun, listLinkedSignals, reportUrl } from "@/lib/api";
import NavChart from "@/components/NavChart";
import DrawdownChart from "@/components/DrawdownChart";
import MetricsTable from "@/components/MetricsTable";
import AllocationTable from "@/components/AllocationTable";
import AutoRefresh from "@/components/AutoRefresh";
import DeleteRunButton from "@/components/DeleteRunButton";
import StatusBadge from "@/components/StatusBadge";
import type {
  BacktestManifest,
  RunDetail,
  RunSummary,
  SignalManifest,
} from "@/lib/types";
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
  let manifestError: string | null = null;
  let linkedSignals: RunSummary[] = [];
  let strategyRun: RunDetail | null = null;
  if (!inProgress && !failed) {
    try {
      manifest = await getManifest(id);
    } catch (err) {
      manifestError = err instanceof Error ? err.message : String(err);
    }
    if (run.kind === "broad_index_backtest") {
      try {
        linkedSignals = await listLinkedSignals(id);
      } catch {
        // Endpoint missing or stale state — render without the section.
      }
    } else if (run.kind === "broad_index_signal" && run.strategy_id) {
      try {
        strategyRun = await getRun(run.strategy_id);
      } catch {
        // Parent strategy was deleted; show the id without a link.
      }
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
      ) : manifestError ? (
        <ManifestMissingPanel error={manifestError} />
      ) : run.kind === "broad_index_backtest" ? (
        <BacktestView
          run={run.label}
          manifest={manifest as BacktestManifest}
          linkedSignals={linkedSignals}
        />
      ) : run.kind === "broad_index_signal" ? (
        <SignalView
          manifest={manifest as SignalManifest}
          strategy={strategyRun}
          rawStrategyId={run.strategy_id ?? null}
        />
      ) : (
        <pre className="table-wrap p-3 text-xs leading-5">
          {JSON.stringify(manifest, null, 2)}
        </pre>
      )}
    </div>
  );
}

function Header({ run, runId }: { run: RunDetail; runId: string }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <Link href="/" className="text-link inline-flex min-h-9 shrink-0 items-center text-sm sm:min-h-10">
          ← 返回
        </Link>
        <div className="min-w-0 flex-1 sm:hidden">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="min-w-0 truncate text-lg font-semibold leading-tight text-slate-950 dark:text-slate-50">
              {run.label}
            </h1>
            <StatusBadge status={run.status} />
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">{kindLabel(run.kind)}</span>
        </div>
      </div>
      <div className="hidden min-w-0 flex-1 sm:block">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="min-w-0 break-words text-xl font-semibold leading-tight text-slate-950 dark:text-slate-50">
            {run.label}
          </h1>
          <StatusBadge status={run.status} />
        </div>
        <span className="text-sm text-slate-500 dark:text-slate-400">{kindLabel(run.kind)}</span>
      </div>
      <div className="toolbar sm:ml-auto">
        {run.report_html_path && (
          <a
            href={reportUrl(runId)}
            target="_blank"
            rel="noreferrer"
            className="btn"
          >
            打开原始 HTML 报告
          </a>
        )}
        <DeleteRunButton runId={runId} kind={run.kind} label={run.label} />
      </div>
    </div>
  );
}

function ProgressPanel({ status }: { status: string }) {
  const label = status === "queued" ? "排队中" : status === "running" ? "运行中" : status;
  return (
    <div className="panel-pad text-sm leading-6 text-slate-700 dark:text-slate-300">
      <div className="mb-1 font-medium text-slate-900 dark:text-slate-100">实验当前状态：{label}…</div>
      <div className="text-slate-500 dark:text-slate-400">
        本页每 2 秒自动刷新一次，运行完成后会自动加载结果。
      </div>
    </div>
  );
}

function ErrorPanel({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900/70 dark:bg-red-950/50 dark:text-red-200">
      <div className="mb-1 font-medium">实验运行失败</div>
      <pre className="overflow-auto whitespace-pre-wrap text-xs leading-5">{error}</pre>
    </div>
  );
}

function ManifestMissingPanel({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/50 dark:text-amber-200">
      <div className="mb-1 font-medium">无法加载本次实验的产物</div>
      <p className="leading-6">
        登记表里仍有这条记录，但产物文件已丢失（可能被手工清理或部分删除）。
        请尝试在列表页删除这条记录后重跑实验。
      </p>
      <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs leading-5">{error}</pre>
    </div>
  );
}

function BacktestView({
  run,
  manifest,
  linkedSignals,
}: {
  run: string;
  manifest: BacktestManifest;
  linkedSignals: RunSummary[];
}) {
  const curve = manifest.curve ?? [];
  const benchmarkCurve = manifest.benchmark_curve ?? [];
  const benchmarkLabel = manifest.benchmark_label ?? "基准";
  const hasBenchmark = benchmarkCurve.length > 0;
  const navSeries: { label: string; points: typeof curve }[] = [
    { label: run, points: curve },
  ];
  if (hasBenchmark) {
    navSeries.push({ label: benchmarkLabel, points: benchmarkCurve });
  }
  const drawdownSeries: { label: string; points: typeof curve }[] = [
    { label: run, points: curve },
  ];
  if (hasBenchmark) {
    drawdownSeries.push({ label: benchmarkLabel, points: benchmarkCurve });
  }
  return (
    <div className="space-y-4">
      <section>
        <h2 className="section-title">
          净值曲线{hasBenchmark ? `（含 ${benchmarkLabel} 对比）` : ""}
        </h2>
        <NavChart series={navSeries} />
      </section>
      <section>
        <h2 className="section-title">
          回撤曲线{hasBenchmark ? `（含 ${benchmarkLabel} 对比）` : ""}
        </h2>
        <DrawdownChart series={drawdownSeries} />
      </section>
      <section>
        <h2 className="section-title">绩效指标</h2>
        <MetricsTable
          columns={[
            { label: "策略", metrics: manifest.metrics },
            ...(manifest.benchmark_metrics
              ? [{ label: benchmarkLabel, metrics: manifest.benchmark_metrics }]
              : []),
          ]}
        />
      </section>
      <LinkedSignals signals={linkedSignals} />
    </div>
  );
}

function LinkedSignals({ signals }: { signals: RunSummary[] }) {
  if (signals.length === 0) {
    return (
      <section>
        <h2 className="section-title">调仓历史</h2>
        <div className="panel-pad text-sm leading-6 text-slate-600 dark:text-slate-300">
          尚未基于此策略生成过当日信号。在
          <Link href="/signal" className="text-link mx-1">
            生成当日信号
          </Link>
          页面选择本策略即可建立绑定。
        </div>
      </section>
    );
  }
  return (
    <section>
      <h2 className="section-title">
        调仓历史（{signals.length}）
      </h2>
      <div className="table-wrap">
        <table className="data-table min-w-[640px]">
          <thead>
            <tr>
              <th>名称</th>
              <th>截至日期</th>
              <th>创建时间</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s) => (
              <tr key={s.id}>
                <td className="px-3 py-2">
                  <Link
                    href={`/runs/${s.id}`}
                    className="text-link inline-flex min-h-11 items-center font-medium sm:min-h-0"
                  >
                    {s.label}
                  </Link>
                </td>
                <td>{s.as_of_date ?? "—"}</td>
                <td>
                  {s.created_at.slice(0, 10)}
                </td>
                <td>{s.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
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

function SignalView({
  manifest,
  strategy,
  rawStrategyId,
}: {
  manifest: SignalManifest;
  strategy: RunDetail | null;
  rawStrategyId: string | null;
}) {
  return (
    <div className="space-y-4">
      {(strategy || rawStrategyId) && (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm leading-6 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/35 dark:text-emerald-100">
          <span className="font-medium">基于策略：</span>{" "}
          {strategy ? (
            <Link
              href={`/runs/${strategy.id}`}
              className="text-link"
            >
              {strategy.label}
            </Link>
          ) : (
            <span className="font-mono text-xs">{rawStrategyId}</span>
          )}
        </section>
      )}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card label="截至日期" value={manifest.as_of} />
        <Card label="总规模" value={formatYi(manifest.total_aum_cny)} />
        <Card label="本次交易笔数" value={String(manifest.trade_count)} />
      </section>
      <section>
        <h2 className="section-title">目标持仓</h2>
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
        <h2 className="section-title">调仓明细</h2>
        <div className="table-wrap">
          <table className="data-table min-w-[860px]">
            <thead>
              <tr>
                <th>板块</th>
                <th>代码</th>
                <th className="text-right">目标权重</th>
                <th className="text-right">当前权重</th>
                <th className="text-right">偏离（pp）</th>
                <th>操作</th>
                <th className="text-right">交易金额</th>
                <th className="text-right">交易股数</th>
              </tr>
            </thead>
            <tbody>
              {manifest.rebalance_lines.map((line) => (
                <tr key={line.ts_code}>
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
    <div className="metric-card">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-1 break-words text-lg font-semibold text-slate-950 dark:text-slate-50">{value}</div>
    </div>
  );
}
