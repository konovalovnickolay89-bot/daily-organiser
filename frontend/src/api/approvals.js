import { request } from "./client.js";

export function listApprovals(status = "pending") {
  return request(`/approvals?status=${encodeURIComponent(status)}`);
}

export function approveRequest(id) {
  return request(`/approvals/${id}/approve`, { method: "POST" });
}

export function skipRequest(id) {
  return request(`/approvals/${id}/skip`, { method: "POST" });
}
