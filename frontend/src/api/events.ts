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

export function listEvents(params: Query = {}) {
  return request(withQuery("/events", params));
}

export function createEvent(body: unknown) {
  return request("/events", { method: "POST", body });
}

export function updateEvent(id: string, body: unknown) {
  return request(`/events/${id}`, { method: "PATCH", body });
}

export function deleteEvent(id: string) {
  return request(`/events/${id}`, { method: "DELETE" });
}
