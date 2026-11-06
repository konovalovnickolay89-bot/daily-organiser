import { request } from "./client";
import type { HouseFacts, SystemState } from "./types";

export function getSystem() {
  return request<SystemState>("/system");
}

export function getHouseFacts() {
  return request<HouseFacts>("/system/facts");
}

export function pauseSystem() {
  return request<SystemState>("/system/pause", { method: "POST" });
}

export function unpauseSystem() {
  return request<SystemState>("/system/unpause", { method: "POST" });
}
