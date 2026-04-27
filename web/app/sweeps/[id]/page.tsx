import Link from "next/link";
import { getManifest, getRun } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import SweepView from "./SweepView";
import type { SweepManifest } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SweepPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [run, manifest] = await Promise.all([getRun(id), getManifest(id)]);
  if (run.kind !== "sweep") {
    return (
      <div className="rounded border bg-white p-4 text-sm">
        <p className="mb-2 font-medium">该实验不是参数扫描类型。</p>
        <Link href={`/runs/${id}`} className="text-blue-600 hover:underline">
          以实验详情页打开 →
        </Link>
      </div>
    );
  }
  const sweep = manifest as SweepManifest;
  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-3 flex-wrap">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← 返回列表
        </Link>
        <h1 className="text-xl font-semibold">{run.label}</h1>
        <StatusBadge status={run.status} />
        <span className="text-sm text-slate-500">
          {sweep.start_date} → {sweep.end_date} · {sweep.schemes.length} 种方案
          × {sweep.bands_pp.length} 个区间
        </span>
      </div>
      <SweepView manifest={sweep} />
    </div>
  );
}
