import { ApiError, request } from "./client.js";

const ASSISTANT_FAILED = "The assistant did not finish. Nothing was changed.";

// GET /agent only reads. It never calls Mistral.
export function getAgent() {
  return request("/agent");
}

function detailFrom(payload) {
  if (payload && typeof payload.detail === "string" && payload.detail.trim()) return payload.detail.trim();
  return "";
}

function messageForFeed(status, payload) {
  const detail = detailFrom(payload);
  if (status === 409 || status === 422 || status === 429 || status === 503) {
    return detail || "The house log could not be reached.";
  }
  if ((status === 424 || status === 200) && detail) return detail;
  return ASSISTANT_FAILED;
}

async function readPayload(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function parseEvent(block) {
  let event = "message";
  const dataLines = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

async function readFeedStream(response, onStep) {
  if (!response.body) throw new ApiError(ASSISTANT_FAILED, response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  let failure = null;

  const take = (block) => {
    const parsed = parseEvent(block);
    if (!parsed) return;
    if (parsed.event === "step" && parsed.data?.step) onStep?.(parsed.data.step);
    else if (parsed.event === "done") result = parsed.data;
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

// One entry. Steps arrive while the assistant works. A failure stays in the panel.
export async function feedAgent(text, { onStep } = {}) {
  onStep?.("received");
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  let response;
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
    return payload;
  }
  return readFeedStream(response, onStep);
}

// Runs the one review GET /agent says is due. The server checks it again.
export function runReview(due) {
  return request("/agent/review", {
    method: "POST",
    body: { trigger: due.trigger, window_key: due.window_key },
  });
}

export function applyProposal(id) {
  return request(`/agent/proposals/${id}/apply`, { method: "POST" });
}

export function dismissProposal(id) {
  return request(`/agent/proposals/${id}/dismiss`, { method: "POST" });
}
