import { request } from "./client";

export type BriefItem = {
  id?: string | null;
  title: string;
  detail?: string | null;
  meta?: string | null;
};

export type BriefSection = {
  key: string;
  title: string;
  placeholder?: boolean;
  summary: string;
  items: BriefItem[];
};

export type MorningBrief = {
  title: string;
  as_of: string;
  house_date: string;
  paused: boolean;
  note?: string | null;
  sections: BriefSection[];
};

export function getMorningBrief() {
  return request<MorningBrief>("/brief/morning");
}
