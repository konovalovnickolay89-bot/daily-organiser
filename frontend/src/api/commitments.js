import { request } from "./client.js";

export function listCommitments(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, String(value));
  }
  const suffix = query.toString();
  return request(suffix ? `/commitments?${suffix}` : "/commitments");
}

export function createCommitment(body) {
  return request("/commitments", { method: "POST", body });
}

export function updateCommitment(id, body) {
  return request(`/commitments/${id}`, { method: "PATCH", body });
}

export function deleteCommitment(id) {
  return request(`/commitments/${id}`, { method: "DELETE" });
}
