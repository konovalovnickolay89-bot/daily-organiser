import { request } from "./client";

export function recordLook() {
  return request("/catch-up/look", { method: "POST" });
}

export function applyCatchUp(id: string) {
  return request(`/catch-up/items/${id}/apply`, { method: "POST" });
}

export function dismissCatchUp(id: string) {
  return request(`/catch-up/items/${id}/dismiss`, { method: "POST" });
}
