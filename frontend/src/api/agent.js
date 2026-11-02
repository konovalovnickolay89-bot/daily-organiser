import { request } from "./client.js";

// GET /agent only reads. It never calls Mistral.
export function getAgent() {
  return request("/agent");
}

export function feedAgent(text) {
  return request("/agent/feed", { method: "POST", body: { text } });
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
