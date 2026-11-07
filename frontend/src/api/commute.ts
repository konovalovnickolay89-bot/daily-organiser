import { request } from "./client";

export type PlaceState = "missing" | "configured" | "unusable";

export type CommutePlace = {
  state: PlaceState;
  check: "not_verified";
  kind?: "coordinates" | "postcode" | null;
  label: string;
  override?: "default" | "used" | "ignored" | null;
  note?: string | null;
};

export type CommuteLeg = {
  role: "outward" | "return";
  time_is: "Arriving" | "Departing";
  target: string;
  clock: string | null;
  minutes: number | null;
  lines: string[];
  detail: string;
  meta: string;
  state: "planned" | "unconnected" | "unavailable" | "no_home";
};

export type CommuteAdvisoryState =
  | "inactive"
  | "paused"
  | "held"
  | "waiting"
  | "fresh"
  | "stale"
  | "error"
  | "limited"
  | "unconfigured";

export type CommuteAdvisory = {
  active: boolean;
  state: CommuteAdvisoryState;
  detail: string;
};

export type CommutePlan = {
  summary: string;
  shift: {
    id: string;
    start: string;
    end: string;
    location_label: string;
    when: "today" | "overnight" | "upcoming";
    overnight: boolean;
  } | null;
  home: CommutePlace;
  destination: CommutePlace;
  arrival_buffer_minutes: number;
  return_buffer_minutes: number;
  outward: CommuteLeg | null;
  back: CommuteLeg | null;
  advisory: CommuteAdvisory;
};

export function getCommutePlan() {
  return request<CommutePlan>("/commute/plan");
}
