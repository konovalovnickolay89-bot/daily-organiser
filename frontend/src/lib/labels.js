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
