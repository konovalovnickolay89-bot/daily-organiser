export const MODE_LABELS = {
  observe: "Observe",
  advise: "Advise",
  prepare: "Prepare",
  execute: "Execute",
};

export const PRIORITY_LABELS = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export const STATUS_LABELS = {
  todo: "To do",
  doing: "Doing",
  done: "Done",
};

export function formatHouseDate(value) {
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

export function taskMeta(task, houseDate) {
  let when = "No date";
  if (task.due_on) {
    if (houseDate && task.due_on < houseDate) when = "Overdue";
    else if (houseDate && task.due_on === houseDate) when = "Due today";
    else when = task.due_on;
  }
  const priority = PRIORITY_LABELS[task.priority] ?? task.priority;
  const status = STATUS_LABELS[task.status] ?? task.status;
  return `${when} · ${priority} · ${status}`;
}
