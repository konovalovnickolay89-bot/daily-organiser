import { request } from "./client";
import type { ApprovalItem } from "./types";

export function listApprovals(status = "pending") {
  return request<{ items: ApprovalItem[] }>(`/approvals?status=${encodeURIComponent(status)}`);
}

export function approveRequest(id: string) {
  return request<{ effect?: { summary?: string } }>(`/approvals/${id}/approve`, { method: "POST" });
}

export function skipRequest(id: string) {
  return request<{ effect?: { summary?: string } }>(`/approvals/${id}/skip`, { method: "POST" });
}
