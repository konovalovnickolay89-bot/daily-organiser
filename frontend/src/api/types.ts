export type TaskStatus = "todo" | "doing" | "done";
export type Priority = "low" | "medium" | "high";
export type CommitmentStatus = "open" | "kept" | "dropped";

export type Task = {
  id: string;
  title: string;
  detail: string | null;
  due_on: string | null;
  priority: Priority;
  status: TaskStatus;
  owner: string;
  created_at: string;
  updated_at: string;
};

export type TaskList = {
  items: Task[];
};

export type TaskWrite = {
  title: string;
  detail: string | null;
  due_on: string | null;
  priority: Priority;
  status: TaskStatus;
};

export type Commitment = {
  id: string;
  title: string;
  detail: string | null;
  due_on: string | null;
  status: CommitmentStatus;
  owner: string;
  source: string;
  created_at: string;
  updated_at: string;
};

export type CommitmentList = {
  items: Commitment[];
};

export type CommitmentWrite = {
  title: string;
  detail: string | null;
  due_on: string | null;
  status: CommitmentStatus;
};

export type SystemState = {
  paused: boolean;
  activity: string;
  status_text: string;
  house_date: string;
  updated_at: string;
  greeting: string;
  greeting_reason: string;
  arrived_at: string | null;
  debounce_until: string | null;
  playlist?: boolean;
};

export type MemoryMatch = {
  id: string;
  kind: string;
  text: string;
};

export type Proposal = {
  id: string;
  origin: string;
  label: string;
  summary: string;
  reason: string;
  date_note?: string | null;
  action?: string;
  memories_used?: number | null;
  matches?: MemoryMatch[];
};

export type AgentDue = {
  trigger: string;
  window_key: string;
  label?: string;
};

export type AgentState = {
  enabled: boolean;
  paused: boolean;
  reachable?: boolean;
  proposals: Proposal[];
  due: AgentDue | null;
  last_reply: { text: string } | null;
};

export type ApprovalItem = {
  id: string;
  mode: string;
  title: string;
  detail?: string | null;
};

export type CatchUpCard = {
  id: string;
  rule: string;
  label: string;
  summary: string;
  reason: string;
  fallback_used?: boolean;
};

export type CatchUpState = {
  paused: boolean;
  quiet: boolean;
  items: CatchUpCard[];
};

export type HouseFacts = {
  timezone: string;
  assistant: "on" | "off";
  assistant_switch: "on" | "off";
  runs_left_today: number;
  diary: "configured" | "not configured";
  weather_location: "configured" | "not configured";
  tfl: "configured" | "not configured";
  banto: "configured" | "not configured";
  voice_input?: "on" | "off";
};

export type XMeter = {
  enabled: boolean;
  connected: boolean;
  credits_remaining: number | null;
  rate_remaining: number | null;
  backing_off: boolean;
  attention?: string | null;
  poll_paused?: boolean;
};

export type HouseStatus = {
  health: "ok" | "degraded";
  version: string;
  last_mistral_success: string | null;
  last_activity_poll: string | null;
  database_bytes: number | null;
  x?: XMeter;
};

export type FeedResult = {
  reply?: string | null;
  proposals?: Proposal[];
};
