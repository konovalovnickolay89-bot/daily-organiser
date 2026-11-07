import { request } from "./client";

export type LineStatusState = "missing" | "fresh" | "stale" | "error";

export type LineFailure = "refused" | "limited" | "timeout" | "malformed" | "upstream";

export type TransitLine = {
  id: string;
  name: string;
  mode: string;
  severity: string;
  reason: string | null;
};

/** Diagnostic read from GET /tfl/status. No key, shift, or location. */
export type LineStatus = {
  configured: boolean;
  state: LineStatusState;
  stale: boolean;
  fetched_at: string | null;
  source_at: string | null;
  failure: LineFailure | null;
  detail: string | null;
  lines: TransitLine[];
};

export function getLineStatus() {
  return request<LineStatus>("/tfl/status");
}
