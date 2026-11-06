import { request } from "./client";

export type HouseAlert = {
  kind: string;
  title: string;
  detail: string;
};

export function listAlerts() {
  return request<{ items: HouseAlert[] }>("/alerts");
}

export function dismissAlert(kind: string) {
  return request<{ items: HouseAlert[] }>(`/alerts/${kind}/dismiss`, { method: "POST" });
}
