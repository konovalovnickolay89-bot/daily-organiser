import { request } from "./client";

export type ShoppingItem = {
  id: string;
  name: string;
  ticked: boolean;
};

export function addShoppingItem(name: string) {
  return request<ShoppingItem>("/shopping", { method: "POST", body: { name } });
}

export function tickShoppingItem(id: string) {
  return request<ShoppingItem>(`/shopping/${id}/tick`, { method: "POST" });
}

export function untickShoppingItem(id: string) {
  return request<ShoppingItem>(`/shopping/${id}/untick`, { method: "POST" });
}
