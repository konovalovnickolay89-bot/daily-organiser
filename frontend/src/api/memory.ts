import { request } from "./client";

export type MemoryKind = "preference" | "fact" | "routine";

export type MemoryItem = {
  id: string;
  kind: MemoryKind | string;
  text: string;
  source: string;
  created_at: string;
  last_used_at: string | null;
  pinned: boolean;
};

export type MemoryExport = {
  exported_at: string;
  items: MemoryItem[];
};

export type MemorySearch = {
  mode: "hybrid" | "fts" | string;
  items: MemoryItem[];
};

export function listMemory(query = "") {
  const q = query.trim();
  const path = q ? `/memory?q=${encodeURIComponent(q)}` : "/memory";
  return request<{ items: MemoryItem[] }>(path);
}

export function searchMemory(query: string) {
  return request<MemorySearch>(`/memory/search?q=${encodeURIComponent(query)}`);
}

export function pinMemory(id: string, pinned: boolean) {
  return request<MemoryItem>(`/memory/${id}`, { method: "PATCH", body: { pinned } });
}

export function forgetMemory(id: string) {
  return request<{ forgotten: boolean }>(`/memory/${id}`, { method: "DELETE" });
}

export function exportMemory() {
  return request<MemoryExport>("/memory/export");
}
