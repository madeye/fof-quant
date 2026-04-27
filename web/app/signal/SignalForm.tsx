"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSignalRun } from "@/lib/api";
import type { CurrentHoldings } from "@/lib/types";

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

export default function SignalForm() {
  const router = useRouter();
  const [holdingsText, setHoldingsText] = useState("");
  const [initialCash, setInitialCash] = useState(1_000_000);
  const [label, setLabel] = useState("");
  const [forceRebalance, setForceRebalance] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let holdings: CurrentHoldings | null = null;
      const trimmed = holdingsText.trim();
      if (trimmed) {
        const parsed = JSON.parse(trimmed);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          !Array.isArray(parsed.positions)
        ) {
          throw new Error("holdings JSON 缺少 positions 数组");
        }
        holdings = parsed as CurrentHoldings;
      }
      const summary = await createSignalRun({
        label: label.trim() ? label.trim() : null,
        holdings,
        initial_cash_if_empty: Number(initialCash),
        cash_buffer: 0.01,
        max_weight: 0.4,
        abs_band_pp: 5.0,
        rel_band_pct: 25.0,
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
      className="space-y-4 rounded border bg-white p-4 max-w-3xl"
    >
      <label className="block text-sm">
        <div className="mb-1 text-slate-700">标签（可选）</div>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="留空将自动生成「当日信号」"
          className="w-full rounded border px-2 py-1"
        />
      </label>
      <label className="block text-sm">
        <div className="mb-1 text-slate-700">
          当前持仓 JSON（可选，留空表示按新资金建仓）
        </div>
        <textarea
          rows={9}
          value={holdingsText}
          onChange={(e) => setHoldingsText(e.target.value)}
          placeholder={HOLDINGS_PLACEHOLDER}
          className="w-full rounded border px-2 py-1 font-mono text-xs"
        />
      </label>
      <label className="block text-sm">
        <div className="mb-1 text-slate-700">无持仓时的初始资金（元）</div>
        <input
          type="number"
          min={1}
          step="1000"
          value={initialCash}
          onChange={(e) => setInitialCash(Number(e.target.value))}
          className="w-full rounded border px-2 py-1"
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
      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "提交中…" : "生成信号"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="rounded border bg-white px-4 py-2 text-sm hover:bg-slate-100"
        >
          取消
        </button>
      </div>
    </form>
  );
}
