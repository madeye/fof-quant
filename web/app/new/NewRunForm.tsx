"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createRun, suggestParams } from "@/lib/api";
import type { BroadIndexBacktestParams } from "@/lib/types";

const DEFAULT_SLEEVE_WEIGHTS = {
  "中证A500": 0.35,
  "中证1000": 0.20,
  "创业板指": 0.15,
  "科创50": 0.15,
  "中证红利低波": 0.15,
};

const TODAY = new Date().toISOString().slice(0, 10);
const DEFAULT_START = "2020-01-02";

type FormState = BroadIndexBacktestParams & {
  sleeve_weights_json: string;
};

// UI percentages: cash_buffer / max_weight are entered as 1.0 / 40 instead of
// 0.01 / 0.4 so the form matches Chinese financial-form convention. We divide
// by 100 before sending to the API.
const INITIAL_STATE: FormState = {
  start_date: DEFAULT_START,
  end_date: TODAY,
  initial_cash: 1_000_000,
  sleeve_weights: null,
  sleeve_weights_json: JSON.stringify(DEFAULT_SLEEVE_WEIGHTS, null, 2),
  cash_buffer: 1, // 1%
  max_weight: 40, // 40%
  abs_band_pp: 5,
  rel_band_pct: 25,
  transaction_cost_bps: 2,
  slippage_bps: 1,
  benchmark_label: "沪深300",
  label: "",
};

export default function NewRunForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onAiSuggest = async () => {
    if (!aiPrompt.trim()) {
      setAiError("请先描述实验意图。");
      return;
    }
    setAiError(null);
    setAiBusy(true);
    try {
      const { params } = await suggestParams(aiPrompt.trim());
      const sleeves = params.sleeve_weights ?? null;
      setForm({
        ...form,
        start_date: params.start_date,
        end_date: params.end_date,
        initial_cash: params.initial_cash,
        sleeve_weights: sleeves,
        sleeve_weights_json: sleeves
          ? JSON.stringify(sleeves, null, 2)
          : form.sleeve_weights_json,
        // LLM returns fractions; UI shows percents.
        cash_buffer: Number((params.cash_buffer * 100).toFixed(2)),
        max_weight: Number((params.max_weight * 100).toFixed(2)),
        abs_band_pp: params.abs_band_pp,
        rel_band_pct: params.rel_band_pct,
        transaction_cost_bps: params.transaction_cost_bps,
        slippage_bps: params.slippage_bps,
        benchmark_label: params.benchmark_label,
        label: params.label ?? "",
      });
    } catch (err) {
      setAiError(err instanceof Error ? err.message : String(err));
    } finally {
      setAiBusy(false);
    }
  };

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let sleeves: Record<string, number> | null = null;
      const trimmed = form.sleeve_weights_json.trim();
      if (trimmed) {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("sleeve_weights must be a JSON object");
        }
        sleeves = Object.fromEntries(
          Object.entries(parsed).map(([k, v]) => [k, Number(v)])
        );
      }
      const summary = await createRun({
        kind: "broad_index_backtest",
        params: {
          start_date: form.start_date,
          end_date: form.end_date,
          initial_cash: Number(form.initial_cash),
          sleeve_weights: sleeves,
          cash_buffer: Number(form.cash_buffer) / 100,
          max_weight: Number(form.max_weight) / 100,
          abs_band_pp: Number(form.abs_band_pp),
          rel_band_pct: Number(form.rel_band_pct),
          transaction_cost_bps: Number(form.transaction_cost_bps),
          slippage_bps: Number(form.slippage_bps),
          benchmark_label: form.benchmark_label,
          label: form.label?.trim() ? form.label.trim() : null,
        },
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
      <section className="rounded border border-blue-200 bg-blue-50 p-3 space-y-2">
        <div className="text-sm font-medium text-blue-900">AI 辅助生成参数</div>
        <textarea
          rows={2}
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          placeholder="例如：稳健低波三年回测，强调中证红利低波；或：激进创业板倾斜五年。"
          className="w-full rounded border px-2 py-1 text-sm"
        />
        {aiError && (
          <div className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800">
            {aiError}
          </div>
        )}
        <button
          type="button"
          onClick={onAiSuggest}
          disabled={aiBusy}
          className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {aiBusy ? "正在生成…" : "AI 生成参数"}
        </button>
        <div className="text-xs text-slate-600">
          需要在 .env 配置 LLM_API_KEY；生成结果仅作建议，提交前可自行调整。
        </div>
      </section>
      <div className="grid grid-cols-2 gap-3">
        <Field label="开始日期">
          <input
            type="date"
            required
            value={form.start_date}
            onChange={(e) => update("start_date", e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="结束日期">
          <input
            type="date"
            required
            value={form.end_date}
            onChange={(e) => update("end_date", e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="初始资金（元）">
          <input
            type="number"
            min={1}
            step="1000"
            value={form.initial_cash}
            onChange={(e) => update("initial_cash", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="基准名称">
          <input
            type="text"
            value={form.benchmark_label}
            onChange={(e) => update("benchmark_label", e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="现金缓冲（%）">
          <input
            type="number"
            min={0}
            max={99.99}
            step="0.1"
            value={form.cash_buffer}
            onChange={(e) => update("cash_buffer", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="单只 ETF 最大权重（%）">
          <input
            type="number"
            min={1}
            max={100}
            step="1"
            value={form.max_weight}
            onChange={(e) => update("max_weight", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="绝对偏离（pp）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.abs_band_pp}
            onChange={(e) => update("abs_band_pp", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="相对偏离（%）">
          <input
            type="number"
            min={0}
            step="1"
            value={form.rel_band_pct}
            onChange={(e) => update("rel_band_pct", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="交易费率（bps）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.transaction_cost_bps}
            onChange={(e) => update("transaction_cost_bps", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
        <Field label="滑点（bps）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.slippage_bps}
            onChange={(e) => update("slippage_bps", Number(e.target.value))}
            className="w-full rounded border px-2 py-1"
          />
        </Field>
      </div>
      <Field label="实验名称（可选）">
        <input
          type="text"
          value={form.label ?? ""}
          onChange={(e) => update("label", e.target.value)}
          placeholder="留空将自动生成"
          className="w-full rounded border px-2 py-1"
        />
      </Field>
      <Field label="板块权重（JSON）">
        <textarea
          rows={6}
          value={form.sleeve_weights_json}
          onChange={(e) => update("sleeve_weights_json", e.target.value)}
          className="w-full rounded border px-2 py-1 font-mono text-xs"
        />
      </Field>
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
          {submitting ? "提交中…" : "开始回测"}
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <div className="mb-1 text-slate-700">{label}</div>
      {children}
    </label>
  );
}
