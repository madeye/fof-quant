import type {
  BroadIndexBacktestParams,
  BroadIndexSignalParams,
  CreateRunPayload,
  Manifest,
  RunDetail,
  RunSummary,
} from "./types";

const BASE = process.env.FOF_API_BASE ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(`${response.status} ${response.statusText} on ${path}: ${detail}`);
  }
  return (await response.json()) as T;
}

export function listRuns(): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>("/api/runs");
}

export function getRun(id: string): Promise<RunDetail> {
  return fetchJson<RunDetail>(`/api/runs/${id}`);
}

export function getManifest(id: string): Promise<Manifest> {
  return fetchJson<Manifest>(`/api/runs/${id}/manifest`);
}

export function reportUrl(id: string): string {
  return `${BASE}/api/runs/${id}/report`;
}

export async function rescan(): Promise<{ added: number; total: number }> {
  return fetchJson<{ added: number; total: number }>("/api/runs/scan", { method: "POST" });
}

export function listLinkedSignals(backtestId: string): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>(`/api/runs/${backtestId}/signals`);
}

export async function createRun(payload: CreateRunPayload): Promise<RunSummary> {
  return fetchJson<RunSummary>("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function createSignalRun(
  params: Partial<BroadIndexSignalParams> = {}
): Promise<RunSummary> {
  return fetchJson<RunSummary>("/api/runs/signal", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ params }),
  });
}

export async function suggestParams(
  prompt: string
): Promise<{ params: BroadIndexBacktestParams }> {
  return fetchJson<{ params: BroadIndexBacktestParams }>("/api/runs/suggest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
}
