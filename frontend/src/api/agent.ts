import { ApiError, request } from "./client";
import type { AgentDue, AgentState, FeedResult } from "./types";

const ASSISTANT_FAILED = "The assistant did not finish. Nothing was changed.";

export function getAgent() {
  return request<AgentState>("/agent");
}

export type ActivityLine = {
  id: string;
  at: string;
  text: string;
  type: string;
};

export function listActivity(limit = 5) {
  return request<{ items: ActivityLine[] }>(`/agent/activity?limit=${limit}`);
}

function detailFrom(payload: { detail?: unknown } | null) {
  if (payload && typeof payload.detail === "string" && payload.detail.trim()) return payload.detail.trim();
  return "";
}

function messageForFeed(status: number, payload: { detail?: unknown } | null) {
  const detail = detailFrom(payload);
  if (status === 409 || status === 422 || status === 429 || status === 503) {
    return detail || "The house log could not be reached.";
  }
  if ((status === 424 || status === 200) && detail) return detail;
  return ASSISTANT_FAILED;
}

async function readPayload(response: Response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as { detail?: unknown };
  } catch {
    return null;
  }
}

type ParsedEvent = {
  event: string;
  data: { step?: string; detail?: string };
};

function parseEvent(block: string): ParsedEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) as ParsedEvent["data"] };
  } catch {
    return null;
  }
}

async function readFeedStream(response: Response, onStep?: (step: string) => void): Promise<FeedResult> {
  if (!response.body) throw new ApiError(ASSISTANT_FAILED, response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: FeedResult | null = null;
  let failure: string | null = null;

  const take = (block: string) => {
    const parsed = parseEvent(block);
    if (!parsed) return;
    if (parsed.event === "step" && parsed.data?.step) onStep?.(parsed.data.step);
    else if (parsed.event === "done") result = parsed.data as FeedResult;
    else if (parsed.event === "error") failure = parsed.data?.detail || ASSISTANT_FAILED;
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) take(part);
  }
  if (buffer.trim()) take(buffer);
  if (failure) throw new ApiError(failure, 424);
  if (!result) throw new ApiError(ASSISTANT_FAILED, 424);
  return result;
}

export async function feedAgent(
  text: string,
  handlers: { onStep?: (step: string) => void } = {},
): Promise<FeedResult> {
  const onStep = handlers.onStep;
  onStep?.("received");
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  let response: Response;
  try {
    response = await fetch(`${base}/agent/feed`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream, application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new ApiError(ASSISTANT_FAILED, 0);
  }

  const type = response.headers.get("content-type") || "";
  if (!response.ok || !type.includes("text/event-stream")) {
    const payload = await readPayload(response);
    if (!response.ok) throw new ApiError(messageForFeed(response.status, payload), response.status);
    onStep?.("calling");
    return (payload ?? {}) as FeedResult;
  }
  return readFeedStream(response, onStep);
}

export function runReview(due: AgentDue) {
  return request("/agent/review", {
    method: "POST",
    body: { trigger: due.trigger, window_key: due.window_key },
  });
}

export function applyProposal(id: string, memoryIds?: string[]) {
  return request<{ applied: { summary: string } }>(`/agent/proposals/${id}/apply`, {
    method: "POST",
    body: memoryIds ? { memory_ids: memoryIds } : undefined,
  });
}

export function dismissProposal(id: string) {
  return request(`/agent/proposals/${id}/dismiss`, { method: "POST" });
}
