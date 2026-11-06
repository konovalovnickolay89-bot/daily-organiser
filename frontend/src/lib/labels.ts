export const MODE_LABELS: Record<string, string> = {
  observe: "Observe",
  advise: "Advise",
  prepare: "Prepare",
  execute: "Execute",
};

export const PRIORITY_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export const STATUS_LABELS: Record<string, string> = {
  todo: "To do",
  doing: "Doing",
  done: "Done",
};

export const COMMITMENT_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  kept: "Kept",
  dropped: "Dropped",
};

export function formatHouseDate(value?: string | null): string {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  if (!match) return String(value);
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(date);
}

type TaskMetaInput = {
  due_on?: string | null;
  priority?: string | null;
  status?: string | null;
};

export function taskMeta(task: TaskMetaInput, houseDate?: string | null): string {
  let when = "No date";
  if (task.due_on) {
    if (houseDate && task.due_on < houseDate) when = "Overdue";
    else if (houseDate && task.due_on === houseDate) when = "Due today";
    else when = task.due_on;
  }
  const priority = task.priority ? (PRIORITY_LABELS[task.priority] ?? task.priority) : task.priority;
  const status = task.status ? (STATUS_LABELS[task.status] ?? task.status) : task.status;
  return `${when} · ${priority} · ${status}`;
}
