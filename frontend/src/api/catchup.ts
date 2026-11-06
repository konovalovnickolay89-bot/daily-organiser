import { request } from "./client";
import type { CatchUpState } from "./types";

export function recordLook() {
  return request<CatchUpState>("/catch-up/look", { method: "POST" });
}

export function applyCatchUp(id: string) {
  return request<{ applied: { summary: string } }>(`/catch-up/items/${id}/apply`, { method: "POST" });
}

export function dismissCatchUp(id: string) {
  return request(`/catch-up/items/${id}/dismiss`, { method: "POST" });
}
