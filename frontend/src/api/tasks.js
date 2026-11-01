import { request } from "./client.js";

function withQuery(path, params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function listTasks(params) {
  return request(withQuery("/tasks", params));
}

export function createTask(body) {
  return request("/tasks", { method: "POST", body });
}

export function getTask(id) {
  return request(`/tasks/${id}`);
}

export function updateTask(id, body) {
  return request(`/tasks/${id}`, { method: "PATCH", body });
}

export function deleteTask(id) {
  return request(`/tasks/${id}`, { method: "DELETE" });
}
