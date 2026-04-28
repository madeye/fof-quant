"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { deleteRun } from "@/lib/api";

export default function DeleteRunButton({
  runId,
  kind,
  label,
}: {
  runId: string;
  kind: string;
  label: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isBacktest = kind === "broad_index_backtest";

  const onDelete = async (cascade: boolean) => {
    const message = cascade
      ? `确认删除「${label}」及其所有调仓历史？此操作不可撤销。`
      : `确认删除「${label}」？此操作不可撤销。`;
    if (!window.confirm(message)) return;
    setError(null);
    setBusy(true);
    try {
      await deleteRun(runId, { cascadeSignals: cascade });
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-stretch gap-1 sm:items-end">
      <div className="toolbar">
        <button
          type="button"
          onClick={() => onDelete(false)}
          disabled={busy}
          className="btn btn-danger"
        >
          {busy ? "删除中…" : "删除"}
        </button>
        {isBacktest && (
          <button
            type="button"
            onClick={() => onDelete(true)}
            disabled={busy}
            className="btn btn-danger"
          >
            删除（含调仓历史）
          </button>
        )}
      </div>
      {error && <span className="text-xs text-red-700">{error}</span>}
    </div>
  );
}
