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

  // Load completed backtests once on mount.
  useEffectOnce(() => {
    (async () => {
      try {
        const runs = await listRuns();
        setBacktests(
          runs.filter(
            (r) => r.kind === "broad_index_backtest" && r.status === "completed"
          )
        );
      } catch (err) {
        // Silent — picker will simply show "无可用回测".
        console.warn("listRuns failed", err);
      }
    })();
  });

  const onPickBacktest = async (runId: string) => {
    setPickedBacktestId(runId);
    setPickError(null);
    if (!runId) return;
    try {
      const detail = await getRun(runId);
      if (!detail.config_yaml) {
        setPickError("该回测没有保存原始配置（可能由 CLI 触发）。");
        return;
      }
      const config = JSON.parse(detail.config_yaml) as {
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
      const summary = await createSignalRun({
        label: label.trim() ? label.trim() : null,
        strategy_id: pickedBacktestId || null,
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
      <section className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
        <div className="text-sm font-medium text-emerald-900">基于已有回测</div>
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
        {pickError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800">
            {pickError}
          </div>
        )}
        <div className="text-xs text-slate-600">
          {backtests.length === 0
            ? "暂无已完成的回测可供选择。"
            : "选择一个已完成的回测，会复制其板块权重、再平衡区间等参数到下方高级设置。"}
        </div>
      </section>
      <label className="block text-sm">
        <div className="mb-1 font-medium text-slate-700">标签（可选）</div>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="留空将自动生成「当日信号」"
          className="w-full"
        />
      </label>
      <label className="block text-sm">
        <div className="mb-1 font-medium text-slate-700">
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
        <div className="mb-1 font-medium text-slate-700">无持仓时的初始资金（元）</div>
        <input
          type="number"
          min={1000}
          step={1000}
          value={initialCash}
          onChange={(e) => setInitialCash(Number(e.target.value))}
          className="w-full"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={forceRebalance}
          onChange={(e) => setForceRebalance(e.target.checked)}
        />
        强制再平衡（忽略 ±5pp / ±25% 偏离阈值）
      </label>

      <button
        type="button"
        onClick={() => setShowAdvanced((v) => !v)}
        className="text-link text-sm font-medium"
      >
        {showAdvanced ? "收起高级设置 ▴" : "展开高级设置 ▾"}
      </button>
      {showAdvanced && (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
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
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
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
      <div className="mb-1 font-medium text-slate-700">{label}</div>
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
