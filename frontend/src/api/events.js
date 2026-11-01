import { request } from "./client.js";

export function listEvents(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, String(value));
  }
  const suffix = query.toString();
  return request(suffix ? `/events?${suffix}` : "/events");
}

export function createEvent(body) {
  return request("/events", { method: "POST", body });
}

export function updateEvent(id, body) {
  return request(`/events/${id}`, { method: "PATCH", body });
}

export function deleteEvent(id) {
  return request(`/events/${id}`, { method: "DELETE" });
}
