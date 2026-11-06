import { request } from "./client";
import type { Commitment, CommitmentList, CommitmentWrite } from "./types";

type Query = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, params: Query = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function listCommitments(params: Query = {}) {
  return request<CommitmentList>(withQuery("/commitments", params));
}

export function createCommitment(body: Partial<CommitmentWrite> & { title: string }) {
  return request<Commitment>("/commitments", { method: "POST", body });
}

export function getCommitment(id: string) {
  return request<Commitment>(`/commitments/${id}`);
}

export function updateCommitment(id: string, body: Partial<CommitmentWrite>) {
  return request<Commitment>(`/commitments/${id}`, { method: "PATCH", body });
}

export function deleteCommitment(id: string) {
  return request<null>(`/commitments/${id}`, { method: "DELETE" });
}
