import { getManifest, listRuns } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type {
  BacktestManifest,
  Manifest,
  RunOverview,
  RunSummary,
  SignalManifest,
  SweepManifest,
} from "@/lib/types";
import RunListClient from "./RunListClient";

export const dynamic = "force-dynamic";

export default async function Home() {
  let runs;
  try {
    runs = await listRuns();
  } catch (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-800">
        <div className="mb-1 font-semibold">无法连接到看板 API。</div>
        <div>
          请先运行{" "}
          <code className="bg-red-100">uv run fof-quant web serve</code>
          ，然后刷新页面。（{String(error)}）
        </div>
      </div>
    );
  }
  const runsWithOverview = await Promise.all(
    runs.map(async (run) => ({
      ...run,
      as_of_display: formatDate(run.as_of_date),
      created_display: formatDate(run.created_at.slice(0, 10)),
      overview: await loadOverview(run),
    }))
  );
  if (runs.length === 0) {
    return (
      <div className="panel-pad text-sm leading-6 text-slate-700">
        <div className="mb-1 font-medium text-slate-900">暂无任何实验记录。</div>
        <div className="break-words">
          先用{" "}
          <code>uv run fof-quant pipeline broad-index</code>
          {" "}或{" "}
          <code>uv run fof-quant analyze broad-index</code>
          {" "}生成一份产物，然后点「刷新」即可看到。
        </div>
      </div>
    );
  }
  return (
    <RunListClient
      initialRuns={runsWithOverview}
    />
  );
}

async function loadOverview(run: RunSummary): Promise<RunOverview> {
  if (run.status !== "completed") {
    return { kind: "empty", message: "运行完成后显示概览" };
  }
  try {
    const manifest = await getManifest(run.id);
    return deriveOverview(run, manifest);
  } catch {
    return { kind: "empty", message: "暂无可用概览" };
  }
}

function deriveOverview(run: RunSummary, manifest: Manifest): RunOverview {
  if (run.kind === "broad_index_backtest") {
    const m = manifest as BacktestManifest;
    return {
      kind: "backtest",
      points: sampleCurve((m.curve ?? []).map((p) => p.nav)),
      total_return: metric(m.metrics, "total_return"),
      annualized_return: metric(m.metrics, "annualized_return"),
      max_drawdown: metric(m.metrics, "max_drawdown"),
      sharpe: metric(m.metrics, "sharpe"),
    };
  }
  if (run.kind === "broad_index_signal") {
    const m = manifest as SignalManifest;
    return {
      kind: "signal",
      total_aum_cny: numberOrNull(m.total_aum_cny),
      trade_count: Number.isFinite(m.trade_count) ? m.trade_count : null,
      holdings: (m.target_plan?.holdings ?? [])
        .map((h) => ({ code: h.etf_code, weight: h.weight }))
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 4),
    };
  }
  if (run.kind === "sweep") {
    const m = manifest as SweepManifest;
    const best = [...(m.rows ?? [])].sort((a, b) => b.sharpe - a.sharpe)[0];
    return {
      kind: "sweep",
      best_scheme: best?.scheme ?? null,
      best_sharpe: numberOrNull(best?.sharpe),
      rows_count: m.rows?.length ?? 0,
    };
  }
  return { kind: "empty", message: "暂无概览" };
}

function metric(metrics: Record<string, number> | null | undefined, key: string) {
  return numberOrNull(metrics?.[key]);
}

function numberOrNull(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sampleCurve(values: number[]): number[] {
  const finite = values.filter((value) => Number.isFinite(value) && value > 0);
  if (finite.length <= 40) return normalize(finite);
  const sampled = Array.from({ length: 40 }, (_, idx) => {
    const sourceIdx = Math.round((idx / 39) * (finite.length - 1));
    return finite[sourceIdx];
  });
  return normalize(sampled);
}

function normalize(values: number[]): number[] {
  const base = values.find((value) => value !== 0);
  if (!base) return [];
  return values.map((value) => value / base);
}
