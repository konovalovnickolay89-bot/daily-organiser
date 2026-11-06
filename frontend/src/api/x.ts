import { request } from "./client";

export type XWatch = {
  id: string;
  kind: "account" | "keyword";
  value: string;
};

export type XStatus = {
  enabled: boolean;
  configured: boolean;
  connected: boolean;
  username: string | null;
  watches: XWatch[];
};

export type XCard = {
  id: string;
  kind: "bookmark" | "watch_match" | "draft";
  summary: string;
  detail: string | null;
  url: string | null;
  expires_at: string | null;
};

export type XCardList = {
  enabled: boolean;
  items: XCard[];
};

export function getXStatus() {
  return request<XStatus>("/x/status");
}

export function startXConnect() {
  return request<{ authorize_url: string }>("/x/connect", { method: "POST" });
}

export function disconnectX() {
  return request<XStatus>("/x/disconnect", { method: "POST" });
}

export function addXWatch(kind: "account" | "keyword", value: string) {
  return request<XWatch>("/x/watches", { method: "POST", body: { kind, value } });
}

export function removeXWatch(id: string) {
  return request<XStatus>(`/x/watches/${id}`, { method: "DELETE" });
}

export function listXItems() {
  return request<XCardList>("/x/items");
}

export function pollX() {
  return request<{ ran: boolean; reason: string }>("/x/poll", { method: "POST" });
}

export function applyXItem(id: string) {
  return request<{ id: string; status: string }>(`/x/items/${id}/apply`, { method: "POST" });
}

export function dismissXItem(id: string) {
  return request<{ id: string; status: string }>(`/x/items/${id}/dismiss`, { method: "POST" });
}

export function postXDraft(id: string) {
  return request<{ id: string; status: string; tweet_id?: string | null }>(`/x/items/${id}/post`, {
    method: "POST",
    body: { confirm: true },
  });
}
