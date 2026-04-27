import NewRunForm from "./NewRunForm";

export default function NewRunPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">New backtest run</h1>
      <p className="text-sm text-slate-600">
        Triggers <code>run_broad_index_backtest_pipeline</code> in the API
        process and writes artifacts under <code>reports/&lt;run_id&gt;/</code>.
        The run starts queued and you&apos;ll be redirected to its detail page.
      </p>
      <NewRunForm />
    </div>
  );
}
