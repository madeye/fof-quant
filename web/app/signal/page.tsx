import SignalForm from "./SignalForm";

export default function SignalPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold leading-tight text-slate-950">生成当日交易信号</h1>
      <p className="max-w-3xl text-sm leading-6 text-slate-600">
        基于宽基缓存数据计算今日的目标持仓与再平衡明细。
        如果填写了当前持仓，系统会按 ±5pp / ±25% 偏离规则计算交易笔数；
        否则按 1,000,000 元资金视为新建仓产出建议持仓。
      </p>
      <SignalForm />
    </div>
  );
}
