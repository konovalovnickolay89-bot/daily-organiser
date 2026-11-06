import { request } from "./client";
import type { Task, TaskList, TaskWrite } from "./types";

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function listTasks(params: Record<string, string | number | boolean | null | undefined> = {}) {
  return request<TaskList>(withQuery("/tasks", params));
}

export function createTask(body: Partial<TaskWrite> & { title: string }) {
  return request<Task>("/tasks", { method: "POST", body });
}

export function getTask(id: string) {
  return request<Task>(`/tasks/${id}`);
}

export function updateTask(id: string, body: Partial<TaskWrite>) {
  return request<Task>(`/tasks/${id}`, { method: "PATCH", body });
}

export function deleteTask(id: string) {
  return request<null>(`/tasks/${id}`, { method: "DELETE" });
}
