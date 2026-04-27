import type { Manifest, RunDetail, RunSummary } from "./types";

const BASE = process.env.FOF_API_BASE ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} on ${path}`);
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
