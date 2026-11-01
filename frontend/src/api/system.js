import { request } from "./client.js";

export function getSystem() {
  return request("/system");
}

export function pauseSystem() {
  return request("/system/pause", { method: "POST" });
}

export function unpauseSystem() {
  return request("/system/unpause", { method: "POST" });
}
