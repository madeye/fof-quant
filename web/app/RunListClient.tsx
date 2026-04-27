"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { rescan } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { kindLabel } from "@/lib/labels";
import type { RunSummary } from "@/lib/types";

type DisplayRun = RunSummary & {
  as_of_display: string;
  created_display: string;
};

export default function RunListClient({
  initialRuns,
}: {
  initialRuns: DisplayRun[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  const selectedIds = Array.from(selected);
  const canCompare = selectedIds.length === 2;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await rescan();
      router.refresh();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Link
          href="/new"
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          + 新建实验
        </Link>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="rounded border bg-white px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50"
        >
          {refreshing ? "刷新中…" : "刷新"}
        </button>
        {canCompare ? (
          <Link
            href={`/compare?ids=${selectedIds.join(",")}`}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            对比
          </Link>
        ) : (
          <span className="text-sm text-slate-500">
            勾选两条记录进行对比（已选 {selectedIds.length} 条）
          </span>
        )}
      </div>
      <div className="overflow-auto rounded border bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 w-8"></th>
              <th className="px-3 py-2 text-left">名称</th>
              <th className="px-3 py-2 text-left">类型</th>
              <th className="px-3 py-2 text-left">截至日期</th>
              <th className="px-3 py-2 text-left">创建时间</th>
              <th className="px-3 py-2 text-left">状态</th>
            </tr>
          </thead>
          <tbody>
            {initialRuns.map((run) => (
              <tr key={run.id} className="border-t hover:bg-slate-50">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(run.id)}
                    onChange={() => toggle(run.id)}
                    aria-label={`选择 ${run.label}`}
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={
                      run.kind === "sweep"
                        ? `/sweeps/${run.id}`
                        : `/runs/${run.id}`
                    }
                    className="text-blue-600 hover:underline"
                  >
                    {run.label}
                  </Link>
                </td>
                <td className="px-3 py-2 text-slate-700">{kindLabel(run.kind)}</td>
                <td className="px-3 py-2 text-slate-700">{run.as_of_display}</td>
                <td className="px-3 py-2 text-slate-700">{run.created_display}</td>
                <td className="px-3 py-2"><StatusBadge status={run.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
