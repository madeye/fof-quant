"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createSignalRun, getRun, listRuns } from "@/lib/api";
import type { CurrentHoldings, RunSummary } from "@/lib/types";

const TODAY = new Date().toISOString().slice(0, 10);
const HOLDINGS_PLACEHOLDER = JSON.stringify(
  {
    as_of: TODAY,
    cash_cny: 50_000,
    positions: [
      { ts_code: "510300.SH", shares: 100_000 },
      { ts_code: "512500.SH", shares: 25_000 },
    ],
  },
  null,
  2
);

const DEFAULT_SLEEVE_WEIGHTS = {
  "中证A500": 0.30,
  "中证1000": 0.15,
  "创业板指": 0.10,
  "科创50": 0.10,
  "中证红利低波": 0.35,
};

type Advanced = {
  sleeve_weights_json: string;
  cash_buffer_pct: number; // UI: percent
  max_weight_pct: number;  // UI: percent
  abs_band_pp: number;
  rel_band_pct: number;
};

const DEFAULT_ADVANCED: Advanced = {
  sleeve_weights_json: JSON.stringify(DEFAULT_SLEEVE_WEIGHTS, null, 2),
  cash_buffer_pct: 1,
  max_weight_pct: 40,
  abs_band_pp: 1,
  rel_band_pct: 25,
};

export default function SignalForm() {
  const router = useRouter();
  const [holdingsText, setHoldingsText] = useState("");
  const [initialCash, setInitialCash] = useState(1_000_000);
  const [label, setLabel] = useState("");
  const [forceRebalance, setForceRebalance] = useState(false);
  const [advanced, setAdvanced] = useState<Advanced>(DEFAULT_ADVANCED);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backtests, setBacktests] = useState<RunSummary[]>([]);
  const [pickedBacktestId, setPickedBacktestId] = useState<string>("");
  const [pickError, setPickError] = useState<string | null>(null);
  const [signals, setSignals] = useState<RunSummary[]>([]);
  const [pickedSignalId, setPickedSignalId] = useState<string>("");
  // strategy_id inherited from the picked previous signal (when one is picked).
  // Falls back to pickedBacktestId on submit so the chain stays bound.
  const [inheritedStrategyId, setInheritedStrategyId] = useState<string | null>(null);

  // Load completed backtests + signals once on mount.
  useEffectOnce(() => {
    (async () => {
      try {
        const runs = await listRuns();
        setBacktests(
          runs.filter(
            (r) => r.kind === "broad_index_backtest" && r.status === "completed"
          )
        );
        setSignals(
          runs.filter(
            (r) => r.kind === "broad_index_signal" && r.status === "completed"
          )
        );
      } catch (err) {
        // Silent — pickers will simply show "无可选项".
        console.warn("listRuns failed", err);
      }
    })();
  });

  // Shared param copy used by both pickers. Reads sleeve_weights / band /
  // cash-buffer / max-weight out of a run's saved config_yaml and writes them
  // into the advanced-settings panel.
  const copyParamsFromConfig = (configYaml: string | null | undefined) => {
    if (!configYaml) return;
    const config = JSON.parse(configYaml) as {
      params?: {
        sleeve_weights?: Record<string, number> | null;
        cash_buffer?: number;
        max_weight?: number;
        abs_band_pp?: number;
        rel_band_pct?: number;
      };
    };
    const params = config.params ?? {};
    setAdvanced((prev) => ({
      sleeve_weights_json: params.sleeve_weights
        ? JSON.stringify(params.sleeve_weights, null, 2)
        : prev.sleeve_weights_json,
      cash_buffer_pct:
        typeof params.cash_buffer === "number"
          ? Number((params.cash_buffer * 100).toFixed(2))
          : prev.cash_buffer_pct,
      max_weight_pct:
        typeof params.max_weight === "number"
          ? Number((params.max_weight * 100).toFixed(2))
          : prev.max_weight_pct,
      abs_band_pp: params.abs_band_pp ?? prev.abs_band_pp,
      rel_band_pct: params.rel_band_pct ?? prev.rel_band_pct,
    }));
    setShowAdvanced(true);
  };

  const onPickBacktest = async (runId: string) => {
    setPickedBacktestId(runId);
    setPickError(null);
    if (!runId) return;
    // Picking a backtest clears any picked previous signal — they're
    // mutually exclusive sources of the strategy binding.
    setPickedSignalId("");
    setInheritedStrategyId(null);
    try {
      const detail = await getRun(runId);
      if (!detail.config_yaml) {
        setPickError("该回测没有保存原始配置（可能由 CLI 触发）。");
        return;
      }
      copyParamsFromConfig(detail.config_yaml);
      if (!label) setLabel(`基于 ${detail.label}`);
    } catch (err) {
      setPickError(err instanceof Error ? err.message : String(err));
    }
  };

  const onPickSignal = async (runId: string) => {
    setPickedSignalId(runId);
    setPickError(null);
    if (!runId) {
      setInheritedStrategyId(null);
      return;
    }
    // Picking a previous signal clears any picked backtest — the new signal
    // inherits the previous signal's strategy_id directly so the chain stays
    // bound to the original backtest.
    setPickedBacktestId("");
    try {
      const detail = await getRun(runId);
      if (!detail.config_yaml) {
        setPickError("该信号没有保存原始配置（可能由 CLI 触发）。");
        return;
      }
      copyParamsFromConfig(detail.config_yaml);
      // Inherit the picked signal's strategy_id so all signals stay bound to
      // the same strategy (the original backtest). If the picked signal has
      // none (one-off), leave inherited null.
      setInheritedStrategyId(detail.strategy_id ?? null);
      if (!label) setLabel(`基于 ${detail.label}`);
    } catch (err) {
      setPickError(err instanceof Error ? err.message : String(err));
    }
  };

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let holdings: CurrentHoldings | null = null;
      const trimmedHoldings = holdingsText.trim();
      if (trimmedHoldings) {
        const parsed = JSON.parse(trimmedHoldings);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          !Array.isArray(parsed.positions)
        ) {
          throw new Error("holdings JSON 缺少 positions 数组");
        }
        holdings = parsed as CurrentHoldings;
      }
      let sleeveWeights: Record<string, number> | null = null;
      const trimmedSleeves = advanced.sleeve_weights_json.trim();
      if (trimmedSleeves) {
        const parsed = JSON.parse(trimmedSleeves);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("sleeve_weights 必须是 JSON 对象");
        }
        sleeveWeights = Object.fromEntries(
          Object.entries(parsed).map(([k, v]) => [k, Number(v)])
        );
      }
      // Strategy binding precedence:
      //   1. previous signal picked → inherit its strategy_id (chain)
      //   2. backtest picked → backtest id IS the strategy_id
      //   3. neither → no strategy binding
      const strategyId = pickedSignalId
        ? inheritedStrategyId
        : pickedBacktestId || null;
      const summary = await createSignalRun({
        label: label.trim() ? label.trim() : null,
        strategy_id: strategyId,
        holdings,
        initial_cash_if_empty: Number(initialCash),
        sleeve_weights: sleeveWeights,
        cash_buffer: advanced.cash_buffer_pct / 100,
        max_weight: advanced.max_weight_pct / 100,
        abs_band_pp: advanced.abs_band_pp,
        rel_band_pct: advanced.rel_band_pct,
        force_rebalance: forceRebalance,
      });
      router.push(`/runs/${summary.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="form-card"
    >
      <section className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900/60 dark:bg-emerald-950/35">
        <div className="text-sm font-medium text-emerald-900 dark:text-emerald-200">
          基于已有回测
        </div>
        <div className="flex items-start gap-2">
          <select
            value={pickedBacktestId}
            onChange={(e) => onPickBacktest(e.target.value)}
            className="min-w-0 flex-1 text-sm"
          >
            <option value="">-- 不基于回测，使用默认参数 --</option>
            {backtests.map((bt) => (
              <option key={bt.id} value={bt.id}>
                {bt.label}（{bt.as_of_date ?? "—"}）
              </option>
            ))}
          </select>
        </div>
        <div className="text-xs leading-5 text-emerald-900/80 dark:text-emerald-100/75">
          {backtests.length === 0
            ? "暂无已完成的回测可供选择。"
            : "选择一个已完成的回测，会复制其板块权重、调仓阈值等参数到下方高级设置；该回测的 ID 将作为新信号的策略归属。"}
        </div>
      </section>
      <section className="space-y-3 rounded-lg border border-sky-200 bg-sky-50 p-3 dark:border-sky-900/60 dark:bg-sky-950/35">
        <div className="text-sm font-medium text-sky-900 dark:text-sky-200">
          基于已有信号
        </div>
        <div className="flex items-start gap-2">
          <select
            value={pickedSignalId}
            onChange={(e) => onPickSignal(e.target.value)}
            className="min-w-0 flex-1 text-sm"
          >
            <option value="">-- 不基于已有信号 --</option>
            {signals.map((sig) => (
              <option key={sig.id} value={sig.id}>
                {sig.label}（{sig.as_of_date ?? "—"}）
                {sig.strategy_id ? "" : "（未绑定策略）"}
              </option>
            ))}
          </select>
        </div>
        <div className="text-xs leading-5 text-sky-900/80 dark:text-sky-100/75">
          {signals.length === 0
            ? "暂无已完成的信号可供选择。"
            : "选择一个已有信号会复制其参数，并继承该信号绑定的策略 ID（即原始回测），" +
              "让多次发出的信号属于同一策略链。与上方「基于已有回测」二选一。"}
        </div>
        {pickError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800 dark:border-red-900/70 dark:bg-red-950/50 dark:text-red-200">
            {pickError}
          </div>
        )}
      </section>
      <label className="block text-sm">
        <div className="mb-1 font-medium text-slate-700 dark:text-slate-300">标签（可选）</div>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="留空将自动生成「当日信号」"
          className="w-full"
        />
      </label>
      <label className="block text-sm">
        <div className="mb-1 font-medium text-slate-700 dark:text-slate-300">
          当前持仓 JSON（可选，留空表示按新资金建仓）
        </div>
        <textarea
          rows={9}
          value={holdingsText}
          onChange={(e) => setHoldingsText(e.target.value)}
          placeholder={HOLDINGS_PLACEHOLDER}
          className="w-full font-mono text-xs"
        />
      </label>
      <label className="block text-sm">
        <div className="mb-1 font-medium text-slate-700 dark:text-slate-300">
          无持仓时的初始资金（元）
        </div>
        <input
          type="number"
          min={1000}
          step={1000}
          value={initialCash}
          onChange={(e) => setInitialCash(Number(e.target.value))}
          className="w-full"
        />
      </label>
      <label className="flex min-h-11 items-center gap-3 rounded-md text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={forceRebalance}
          onChange={(e) => setForceRebalance(e.target.checked)}
          className="size-5 min-h-0 shadow-none"
        />
        强制调仓（忽略 ±1pp / ±25% 偏离阈值）
      </label>

      <button
        type="button"
        onClick={() => setShowAdvanced((v) => !v)}
        className="btn self-start"
      >
        {showAdvanced ? "收起高级设置 ▴" : "展开高级设置 ▾"}
      </button>
      {showAdvanced && (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
          <div className="form-grid">
            <Field label="现金缓冲（%）">
              <input
                type="number"
                min={0}
                max={99.99}
                step="0.1"
                value={advanced.cash_buffer_pct}
                onChange={(e) =>
                  setAdvanced((p) => ({ ...p, cash_buffer_pct: Number(e.target.value) }))
                }
                className="w-full"
              />
            </Field>
            <Field label="单只 ETF 最大权重（%）">
              <input
                type="number"
                min={1}
                max={100}
                step="1"
                value={advanced.max_weight_pct}
                onChange={(e) =>
                  setAdvanced((p) => ({ ...p, max_weight_pct: Number(e.target.value) }))
                }
                className="w-full"
              />
            </Field>
            <Field label="绝对偏离（pp）">
              <input
                type="number"
                min={0}
                step="0.5"
                value={advanced.abs_band_pp}
                onChange={(e) =>
                  setAdvanced((p) => ({ ...p, abs_band_pp: Number(e.target.value) }))
                }
                className="w-full"
              />
            </Field>
            <Field label="相对偏离（%）">
              <input
                type="number"
                min={0}
                step="1"
                value={advanced.rel_band_pct}
                onChange={(e) =>
                  setAdvanced((p) => ({ ...p, rel_band_pct: Number(e.target.value) }))
                }
                className="w-full"
              />
            </Field>
          </div>
          <Field label="板块权重（JSON）">
            <textarea
              rows={6}
              value={advanced.sleeve_weights_json}
              onChange={(e) =>
                setAdvanced((p) => ({ ...p, sleeve_weights_json: e.target.value }))
              }
              className="w-full font-mono text-xs"
            />
          </Field>
        </section>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/70 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </div>
      )}
      <div className="toolbar">
        <button
          type="submit"
          disabled={submitting}
          className="btn btn-primary px-4"
        >
          {submitting ? "提交中…" : "生成信号"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="btn px-4"
        >
          取消
        </button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <div className="mb-1 font-medium text-slate-700 dark:text-slate-300">{label}</div>
      {children}
    </label>
  );
}

// Strict-mode-safe effect that runs exactly once on mount.
function useEffectOnce(fn: () => void) {
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    fn();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
