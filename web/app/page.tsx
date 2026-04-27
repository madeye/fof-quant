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
        <div className="font-semibold mb-1">无法连接到看板 API。</div>
        <div>
          请先运行{" "}
          <code className="bg-red-100 px-1">uv run fof-quant web serve</code>
          ，然后刷新页面。（{String(error)}）
        </div>
      </div>
    );
  }
  if (runs.length === 0) {
    return (
      <div className="rounded border bg-white p-6 text-sm text-slate-700">
        <div className="font-medium mb-1">暂无任何实验记录。</div>
        <div>
          先用{" "}
          <code className="bg-slate-100 px-1">uv run fof-quant pipeline broad-index</code>
          {" "}或{" "}
          <code className="bg-slate-100 px-1">uv run fof-quant analyze broad-index</code>
          {" "}生成一份产物，然后点「刷新」即可看到。
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
    />
  );
}
