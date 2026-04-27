import NewRunForm from "./NewRunForm";

export default function NewRunPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">新建回测实验</h1>
      <p className="text-sm text-slate-600">
        提交后会调用 <code>run_broad_index_backtest_pipeline</code> 在 API 进程中后台执行，
        产物写入 <code>reports/&lt;run_id&gt;/</code> 目录。任务会先进入「排队中」状态，
        系统将自动跳转到该实验的详情页。
      </p>
      <NewRunForm />
    </div>
  );
}
