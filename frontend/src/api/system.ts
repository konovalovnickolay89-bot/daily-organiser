import { request } from "./client";
import type { HouseFacts, HouseStatus, SystemState } from "./types";

export type { HouseStatus };

export function getSystem() {
  return request<SystemState>("/system");
}

export function getHouseFacts() {
  return request<HouseFacts>("/system/facts");
}

export function getStatus() {
  return request<HouseStatus>("/system/status");
}

export function pauseSystem() {
  return request<SystemState>("/system/pause", { method: "POST" });
}

export function unpauseSystem() {
  return request<SystemState>("/system/unpause", { method: "POST" });
}

export function setAssistantSwitch(enabled: boolean) {
  return request<HouseFacts>("/system/assistant", { method: "POST", body: { enabled } });
}

export type CalendarEntry = {
  id: string | null;
  name: string;
  enabled: boolean;
};

export type CalendarList = {
  configured: boolean;
  using_primary: boolean;
  items: CalendarEntry[];
};

export function listCalendars() {
  return request<CalendarList>("/system/calendars");
}

export function addCalendar(name: string) {
  return request<CalendarList>("/system/calendars", { method: "POST", body: { name } });
}

export function removeCalendar(id: string) {
  return request<CalendarList>(`/system/calendars/${id}`, { method: "DELETE" });
}

export type FeatureSettings = {
  playlist: {
    enabled: boolean;
    available: boolean;
    source: string;
    profile: string;
    detail: string;
  };
  alerts: { enabled: boolean };
  webhooks: { enabled: boolean; banto: string; banto_x: string };
  voice: { mic: "on" | "off"; env_enabled: boolean; voxtral: string; detail: string };
  x: {
    enabled: boolean;
    sync_minutes: number;
    daily_cap: number;
    from_max: number;
    draft_expiry_days: number;
    detail: string;
  };
  agent_context: {
    token_budget: number;
    memory_limit: number;
    smart_add_days: number;
    catch_up_days: number;
  };
  docs: { state: string; detail: string };
};

export function getFeatureSettings() {
  return request<FeatureSettings>("/system/settings");
}

export function patchFeatureSettings(body: Record<string, boolean | number>) {
  return request<FeatureSettings>("/system/settings", { method: "PATCH", body });
}
