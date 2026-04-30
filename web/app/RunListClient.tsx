"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { deleteRun, rescan } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { kindLabel } from "@/lib/labels";
import { formatMoney, formatPct, formatRatio } from "@/lib/format";
import type { RunOverview, RunSummary } from "@/lib/types";

type DisplayRun = RunSummary & {
  as_of_display: string;
  created_display: string;
  overview: RunOverview;
};

export default function RunListClient({
  initialRuns,
}: {
  initialRuns: DisplayRun[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedIds = Array.from(selected);
  const canCompare = selectedIds.length === 2;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await rescan();
      router.refresh();
    } finally {
      setRefreshing(false);
    }
  };

  const onDeleteRow = async (run: DisplayRun) => {
    if (!window.confirm(`确认删除「${run.label}」？此操作不可撤销。`)) return;
    setError(null);
    setDeletingId(run.id);
    try {
      const cascade = run.kind === "broad_index_backtest";
      await deleteRun(run.id, { cascadeSignals: cascade });
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(run.id);
        return next;
      });
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  };

  const onBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `确认删除选中的 ${selectedIds.length} 条记录？回测的关联调仓也会一并删除。此操作不可撤销。`
      )
    )
      return;
    setError(null);
    setBulkDeleting(true);
    try {
      const lookup = new Map(initialRuns.map((r) => [r.id, r] as const));
      for (const id of selectedIds) {
        const run = lookup.get(id);
        const cascade = run?.kind === "broad_index_backtest";
        await deleteRun(id, { cascadeSignals: cascade });
      }
      setSelected(new Set());
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBulkDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold leading-tight text-slate-950 dark:text-slate-50">
            实验看板
          </h1>
          <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
            {initialRuns.length} 条实验记录，卡片内展示关键指标和缩略概览。
          </p>
        </div>
        <div className="toolbar">
          <Link href="/new" className="btn btn-primary">
            + 新建实验
          </Link>
          <Link href="/signal" className="btn btn-success">
            + 当日信号
          </Link>
          <button onClick={refresh} disabled={refreshing} className="btn">
            {refreshing ? "刷新中…" : "刷新"}
          </button>
          {canCompare ? (
            <Link
              href={`/compare?ids=${selectedIds.join(",")}`}
              className="btn btn-primary"
            >
              对比
            </Link>
          ) : (
            <span className="text-sm leading-6 text-slate-500 dark:text-slate-400">
              勾选两条进行对比（已选 {selectedIds.length} 条）
            </span>
          )}
          {selectedIds.length > 0 && (
            <button
              onClick={onBulkDelete}
              disabled={bulkDeleting}
              className="btn btn-danger"
            >
              {bulkDeleting ? "删除中…" : `删除选中 (${selectedIds.length})`}
            </button>
          )}
        </div>
      </div>
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/70 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {initialRuns.map((run) => (
          <article key={run.id} className="run-card">
            <div className="flex items-start gap-3">
              <label className="-m-2 flex min-h-11 min-w-11 shrink-0 items-start justify-center p-2">
                <input
                  type="checkbox"
                  checked={selected.has(run.id)}
                  onChange={() => toggle(run.id)}
                  aria-label={`选择 ${run.label}`}
                  className="mt-1 size-5 min-h-0 shadow-none"
                />
              </label>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={run.status} />
                  <span className="run-card-muted">{kindLabel(run.kind)}</span>
                </div>
                <Link
                  href={
                    run.kind === "sweep"
                      ? `/sweeps/${run.id}`
                      : `/runs/${run.id}`
                  }
                  className="mt-2 block break-words text-base font-semibold leading-snug text-slate-950 hover:text-blue-700 dark:text-slate-50 dark:hover:text-blue-300"
                >
                  {run.label}
                </Link>
              </div>
            </div>

            <OverviewPanel overview={run.overview} />

            <div className="mt-auto grid grid-cols-2 gap-2 pt-4 text-sm">
              <Meta label="截至日期" value={run.as_of_display} />
              <Meta label="创建时间" value={run.created_display} />
            </div>

            <div className="mt-4 flex items-center justify-between gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
              <Link
                href={
                  run.kind === "sweep"
                    ? `/sweeps/${run.id}`
                    : `/runs/${run.id}`
                }
                className="btn"
              >
                查看详情
              </Link>
              <button
                onClick={() => onDeleteRow(run)}
                disabled={deletingId === run.id || bulkDeleting}
                className="btn btn-danger"
              >
                {deletingId === run.id ? "删除中…" : "删除"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function OverviewPanel({ overview }: { overview: RunOverview }) {
  if (overview.kind === "backtest") {
    return (
      <div className="mt-4 space-y-3">
        <Sparkline values={overview.points} />
        <div className="grid grid-cols-2 gap-2">
          <Metric label="总收益" value={formatNullablePct(overview.total_return)} />
          <Metric label="年化收益" value={formatNullablePct(overview.annualized_return)} />
          <Metric label="最大回撤" value={formatNullablePct(overview.max_drawdown)} tone="risk" />
          <Metric label="夏普" value={formatNullableRatio(overview.sharpe)} />
        </div>
      </div>
    );
  }

  if (overview.kind === "signal") {
    return (
      <div className="mt-4 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Metric
            label="组合规模"
            value={
              overview.total_aum_cny == null
                ? "—"
                : formatMoney(overview.total_aum_cny)
            }
          />
          <Metric
            label="交易笔数"
            value={overview.trade_count == null ? "—" : String(overview.trade_count)}
          />
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
          <div className="mb-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            目标持仓 Top
          </div>
          <div className="space-y-2">
            {overview.holdings.length > 0 ? (
              overview.holdings.map((holding) => (
                <div key={holding.code} className="space-y-1">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-mono text-slate-700 dark:text-slate-300">
                      {holding.code}
                    </span>
                    <span className="tabular-nums text-slate-500 dark:text-slate-400">
                      {formatPct(holding.weight, 1)}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-800">
                    <div
                      className="h-1.5 rounded-full bg-emerald-500"
                      style={{ width: `${Math.max(4, Math.min(100, holding.weight * 100))}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-500 dark:text-slate-400">
                暂无持仓数据
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (overview.kind === "sweep") {
    return (
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Metric label="方案数" value={String(overview.rows_count)} />
        <Metric label="最佳夏普" value={formatNullableRatio(overview.best_sharpe)} />
        <div className="col-span-2 rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
            最佳方案
          </div>
          <div className="mt-1 break-words text-sm font-semibold text-slate-800 dark:text-slate-100">
            {overview.best_scheme ?? "—"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 flex min-h-40 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
      {overview.message}
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const gradientId = useId().replace(/:/g, "");
  if (values.length < 2) {
    return (
      <div className="flex h-36 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
        暂无收益曲线
      </div>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((value, idx) => {
      const x = (idx / (values.length - 1)) * 100;
      const y = 92 - ((value - min) / span) * 76;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const last = values[values.length - 1];
  const first = values[0];
  const positive = last >= first;
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
      <div className="mb-2 flex items-center justify-between gap-2 text-xs">
        <span className="font-medium text-slate-500 dark:text-slate-400">
          收益曲线缩略图
        </span>
        <span
          className={
            "tabular-nums " +
            (positive ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400")
          }
        >
          {formatPct(last / first - 1, 1)}
        </span>
      </div>
      <svg viewBox="0 0 100 100" className="h-28 w-full overflow-visible" role="img">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={positive ? "#10b981" : "#ef4444"} stopOpacity="0.28" />
            <stop offset="100%" stopColor={positive ? "#10b981" : "#ef4444"} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline
          points={`0,96 ${points} 100,96`}
          fill={`url(#${gradientId})`}
          stroke="none"
        />
        <polyline
          points={points}
          fill="none"
          stroke={positive ? "#10b981" : "#ef4444"}
          strokeWidth="2.4"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "risk";
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
      <div
        className={
          "mt-1 break-words text-sm font-semibold tabular-nums " +
          (tone === "risk"
            ? "text-red-600 dark:text-red-400"
            : "text-slate-900 dark:text-slate-100")
        }
      >
        {value}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-sm text-slate-700 dark:text-slate-300">{value}</div>
    </div>
  );
}

function formatNullablePct(value: number | null): string {
  return value == null ? "—" : formatPct(value);
}

function formatNullableRatio(value: number | null): string {
  return value == null ? "—" : formatRatio(value);
}
