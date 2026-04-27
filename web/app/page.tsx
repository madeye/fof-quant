import Link from "next/link";
import { listRuns } from "@/lib/api";
import { formatDate } from "@/lib/format";
import RunListClient from "./RunListClient";

export const dynamic = "force-dynamic";

export default async function Home() {
  let runs;
  try {
    runs = await listRuns();
  } catch (error) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <div className="font-semibold mb-1">Cannot reach the dashboard API.</div>
        <div>
          Start it with{" "}
          <code className="bg-red-100 px-1">uv run fof-quant web serve</code> and
          reload. ({String(error)})
        </div>
      </div>
    );
  }
  if (runs.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-sm text-slate-700">
        <div className="font-medium mb-1">No runs found yet.</div>
        <div>
          Generate a run with{" "}
          <code className="bg-slate-100 px-1">uv run fof-quant pipeline broad-index</code>
          {" "}or{" "}
          <code className="bg-slate-100 px-1">uv run fof-quant analyze broad-index</code>
          , then click Refresh.
        </div>
      </div>
    );
  }
  return (
    <RunListClient
      initialRuns={runs.map((r) => ({
        ...r,
        as_of_display: formatDate(r.as_of_date),
        created_display: formatDate(r.created_at.slice(0, 10)),
      }))}
    >
      {(run) => (
        <Link
          href={run.kind === "sweep" ? `/sweeps/${run.id}` : `/runs/${run.id}`}
          className="text-blue-600 hover:underline"
        >
          {run.label}
        </Link>
      )}
    </RunListClient>
  );
}
