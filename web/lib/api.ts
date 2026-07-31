import type {
  BroadIndexBacktestParams,
  BroadIndexSignalParams,
  CreateRunPayload,
  Manifest,
  RunDetail,
  RunSummary,
} from "./types";

// Server-side (RSC, server actions) talks to the API directly via loopback
// using FOF_API_BASE. Browser-side uses the empty string so requests go
// same-origin and nginx routes /api/* (except /api/auth/*) to the backend.
const SERVER_BASE = process.env.FOF_API_BASE ?? "http://127.0.0.1:8000";
const BASE = typeof window === "undefined" ? SERVER_BASE : "";

// Read the body once as text, then try to parse JSON. Calling .json() and
// then .text() on the same Response throws "Body is disturbed or locked"
// because the underlying stream is already consumed — surface the real
// error instead.
async function readErrorDetail(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) return "";
  try {
    const body = JSON.parse(raw);
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      return typeof d === "string" ? d : JSON.stringify(d);
    }
    return JSON.stringify(body);
  } catch {
    return raw;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
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
  // Always relative — this URL is embedded in an <a href> rendered for the
  // browser, so it must resolve against the page origin (https://...) and
  // not the loopback address used for server-side fetches.
  return `/api/runs/${id}/report`;
}

export async function rescan(): Promise<{ added: number; total: number }> {
  return fetchJson<{ added: number; total: number }>("/api/runs/scan", { method: "POST" });
}

export function listLinkedSignals(backtestId: string): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>(`/api/runs/${backtestId}/signals`);
}

export async function deleteRun(
  id: string,
  options: { cascadeSignals?: boolean } = {}
): Promise<void> {
  const qs = options.cascadeSignals ? "?cascade_signals=true" : "";
  const response = await fetch(`${BASE}/api/runs/${id}${qs}`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
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
