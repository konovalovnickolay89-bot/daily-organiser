import { request } from "./client";

export function listApprovals(status = "pending") {
  return request(`/approvals?status=${encodeURIComponent(status)}`);
}

export function approveRequest(id: string) {
  return request(`/approvals/${id}/approve`, { method: "POST" });
}

export function skipRequest(id: string) {
  return request(`/approvals/${id}/skip`, { method: "POST" });
}
