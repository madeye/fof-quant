import type { RunStatus } from "@/lib/types";

const PALETTE: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function StatusBadge({ status }: { status: RunStatus }) {
  const className = PALETTE[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${className}`}>
      {status}
    </span>
  );
}
