import { request } from "./client";

type Query = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, params: Query = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function listActionRequests(params: Query = {}) {
  return request(withQuery("/action-requests", params));
}

export function createActionRequest(body: unknown) {
  return request("/action-requests", { method: "POST", body });
}

export function updateActionRequest(id: string, body: unknown) {
  return request(`/action-requests/${id}`, { method: "PATCH", body });
}

export function deleteActionRequest(id: string) {
  return request(`/action-requests/${id}`, { method: "DELETE" });
}
