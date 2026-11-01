import { request } from "./client.js";

export function listActionRequests(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, String(value));
  }
  const suffix = query.toString();
  return request(suffix ? `/action-requests?${suffix}` : "/action-requests");
}

export function createActionRequest(body) {
  return request("/action-requests", { method: "POST", body });
}

export function updateActionRequest(id, body) {
  return request(`/action-requests/${id}`, { method: "PATCH", body });
}

export function deleteActionRequest(id) {
  return request(`/action-requests/${id}`, { method: "DELETE" });
}
