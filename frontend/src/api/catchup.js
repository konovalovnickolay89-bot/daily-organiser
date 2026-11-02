import { request } from "./client.js";

// POST /catch-up/look records a look. It never calls Mistral.
export function recordLook() {
  return request("/catch-up/look", { method: "POST" });
}

export function applyCatchUp(id) {
  return request(`/catch-up/items/${id}/apply`, { method: "POST" });
}

export function dismissCatchUp(id) {
  return request(`/catch-up/items/${id}/dismiss`, { method: "POST" });
}
