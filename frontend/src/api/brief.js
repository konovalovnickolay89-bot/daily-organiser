import { request } from "./client.js";

export function getMorningBrief() {
  return request("/brief/morning");
}
