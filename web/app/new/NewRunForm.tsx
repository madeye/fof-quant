"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createRun, suggestParams } from "@/lib/api";
import type { BroadIndexBacktestParams } from "@/lib/types";

const DEFAULT_SLEEVE_WEIGHTS = {
  "中证A500": 0.30,
  "中证1000": 0.15,
  "创业板指": 0.10,
  "科创50": 0.10,
  "中证红利低波": 0.35,
};

// Chinese labels for the predefined sleeve schemes — shown in the bull/bear
// dropdowns. Keep keys in sync with the SCHEMES map below.
const SCHEME_LABELS: Record<string, string> = {
  balanced_5: "balanced_5（均衡 5 板块）",
  core_300_only: "core_300_only（沪深 300 单押）",
  core_satellite: "core_satellite（核心-卫星）",
  growth_tilt: "growth_tilt（成长倾斜）",
  defensive: "defensive（防守）",
  equal_5: "equal_5（等权 5 板块）",
  dividend_heavy: "dividend_heavy（红利重仓）",
};

// Predefined sleeve schemes for the regime overlay's bull/bear inputs.
// Mirrors fof_quant.analysis.sweep.SCHEMES; keep the two in sync.
const SCHEMES: Record<string, Record<string, number>> = {
  balanced_5: {
    "中证A500": 0.35,
    "中证1000": 0.20,
    "创业板指": 0.15,
    "科创50": 0.15,
    "中证红利低波": 0.15,
  },
  core_300_only: { "沪深300": 1.00 },
  core_satellite: {
    "沪深300": 0.50,
    "中证1000": 0.20,
    "创业板指": 0.15,
    "中证红利低波": 0.15,
  },
  growth_tilt: {
    "中证A500": 0.20,
    "中证1000": 0.20,
    "创业板指": 0.30,
    "科创50": 0.20,
    "中证红利低波": 0.10,
  },
  defensive: {
    "上证50": 0.30,
    "中证A500": 0.30,
    "中证红利低波": 0.30,
    "中证1000": 0.10,
  },
  equal_5: {
    "中证A500": 0.20,
    "中证1000": 0.20,
    "创业板指": 0.20,
    "科创50": 0.20,
    "中证红利低波": 0.20,
  },
  dividend_heavy: {
    "中证A500": 0.30,
    "中证1000": 0.15,
    "创业板指": 0.10,
    "科创50": 0.10,
    "中证红利低波": 0.35,
  },
};

const TODAY = new Date().toISOString().slice(0, 10);
const DEFAULT_START = "2020-01-02";

type FormState = Omit<
  BroadIndexBacktestParams,
  "regime_kind" | "bull_sleeve_weights" | "bear_sleeve_weights"
> & {
  sleeve_weights_json: string;
  // UI uses "" for "no overlay"; submit-time code maps "" → null payload.
  regime_kind: "" | "sma200";
  bull_scheme: string;
  bear_scheme: string;
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
  abs_band_pp: 1,
  rel_band_pct: 25,
  transaction_cost_bps: 2,
  slippage_bps: 1,
  benchmark_label: "沪深300",
  label: "",
  regime_kind: "",
  bull_scheme: "equal_5",
  bear_scheme: "defensive",
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
      const regimeOn = form.regime_kind === "sma200";
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
          regime_kind: regimeOn ? "sma200" : null,
          bull_sleeve_weights: regimeOn ? SCHEMES[form.bull_scheme] : null,
          bear_sleeve_weights: regimeOn ? SCHEMES[form.bear_scheme] : null,
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
      className="form-card"
    >
      <section className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
        <div className="text-sm font-medium text-blue-900">AI 辅助生成参数</div>
        <textarea
          rows={2}
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          placeholder="例如：稳健低波三年回测，强调中证红利低波；或：激进创业板倾斜五年。"
          className="w-full text-sm"
        />
        {aiError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800">
            {aiError}
          </div>
        )}
        <button
          type="button"
          onClick={onAiSuggest}
          disabled={aiBusy}
          className="btn btn-primary text-sm"
        >
          {aiBusy ? "正在生成…" : "AI 生成参数"}
        </button>
        <div className="text-xs text-slate-600">
          需要在 .env 配置 LLM_API_KEY；生成结果仅作建议，提交前可自行调整。
        </div>
      </section>
      <div className="form-grid">
        <Field label="开始日期">
          <input
            type="date"
            required
            value={form.start_date}
            onChange={(e) => update("start_date", e.target.value)}
            className="w-full"
          />
        </Field>
        <Field label="结束日期">
          <input
            type="date"
            required
            value={form.end_date}
            onChange={(e) => update("end_date", e.target.value)}
            className="w-full"
          />
        </Field>
        <Field label="初始资金（元）">
          <input
            type="number"
            min={1000}
            step={1000}
            value={form.initial_cash}
            onChange={(e) => update("initial_cash", Number(e.target.value))}
            className="w-full"
          />
        </Field>
        <Field label="基准名称">
          <input
            type="text"
            value={form.benchmark_label}
            onChange={(e) => update("benchmark_label", e.target.value)}
            className="w-full"
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
            className="w-full"
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
            className="w-full"
          />
        </Field>
        <Field label="绝对偏离（pp）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.abs_band_pp}
            onChange={(e) => update("abs_band_pp", Number(e.target.value))}
            className="w-full"
          />
        </Field>
        <Field label="相对偏离（%）">
          <input
            type="number"
            min={0}
            step="1"
            value={form.rel_band_pct}
            onChange={(e) => update("rel_band_pct", Number(e.target.value))}
            className="w-full"
          />
        </Field>
        <Field label="交易费率（bps）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.transaction_cost_bps}
            onChange={(e) => update("transaction_cost_bps", Number(e.target.value))}
            className="w-full"
          />
        </Field>
        <Field label="滑点（bps）">
          <input
            type="number"
            min={0}
            step="0.5"
            value={form.slippage_bps}
            onChange={(e) => update("slippage_bps", Number(e.target.value))}
            className="w-full"
          />
        </Field>
      </div>
      <section className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
        <div className="text-sm font-medium text-amber-900">
          牛熊切换信号
        </div>
        <div className="text-xs leading-5 text-amber-800">
          开启后忽略上方的板块权重 JSON，按 200 日均线 ±5%/3% 滞回阈值信号，
          牛市切换到牛市配方、熊市切换到熊市配方。滚动样本外验证：
          牛市=equal_5 / 熊市=defensive 在 2022–2026 测试期夏普比率 0.85、
          卡玛比率 0.98。
        </div>
        <div className="form-grid">
          <Field label="信号类型">
            <select
              value={form.regime_kind}
              onChange={(e) =>
                update("regime_kind", e.target.value as FormState["regime_kind"])
              }
              className="w-full"
            >
              <option value="">关闭（使用静态板块权重）</option>
              <option value="sma200">200 日均线 + 5%/3% 滞回阈值</option>
            </select>
          </Field>
          <Field label="牛市配方">
            <select
              value={form.bull_scheme}
              disabled={form.regime_kind === ""}
              onChange={(e) => update("bull_scheme", e.target.value)}
              className="w-full disabled:bg-slate-100"
            >
              {Object.entries(SCHEMES).map(([name]) => (
                <option key={name} value={name}>
                  {SCHEME_LABELS[name] ?? name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="熊市配方">
            <select
              value={form.bear_scheme}
              disabled={form.regime_kind === ""}
              onChange={(e) => update("bear_scheme", e.target.value)}
              className="w-full disabled:bg-slate-100"
            >
              {Object.entries(SCHEMES).map(([name]) => (
                <option key={name} value={name}>
                  {SCHEME_LABELS[name] ?? name}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </section>
      <Field label="实验名称（可选）">
        <input
          type="text"
          value={form.label ?? ""}
          onChange={(e) => update("label", e.target.value)}
          placeholder="留空将自动生成"
          className="w-full"
        />
      </Field>
      <Field label="板块权重（JSON）">
        <textarea
          rows={6}
          value={form.sleeve_weights_json}
          onChange={(e) => update("sleeve_weights_json", e.target.value)}
          className="w-full font-mono text-xs"
        />
      </Field>
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
          {submitting ? "提交中…" : "开始回测"}
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
