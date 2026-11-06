import { useEffect, useId, useRef, useState } from "react";
import { createTask, deleteTask, getTask, updateTask } from "../../api/tasks";
import type { Priority, TaskStatus, TaskWrite } from "../../api/types";
import { cx, dialog, dialogActions, errorText, fieldHint, fieldInput, fieldLabel, fieldStack, ghost, heading, kickerMuted, lede, primary } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { DatePassedNote } from "../../components/DatePassedNote";
import { useHouse } from "../../house/HouseContext";
import { useHouseDialog } from "../../lib/dialog";
import { asError } from "../../lib/errors";
import { PRIORITY_LABELS, STATUS_LABELS } from "../../lib/labels";
import { useUndo } from "./UndoToast";

const PRIORITIES: Priority[] = ["low", "medium", "high"];
const STATUSES: TaskStatus[] = ["todo", "doing", "done"];

type TaskForm = {
  title: string;
  detail: string;
  due_on: string;
  priority: Priority;
  status: TaskStatus;
};

function bodyFrom(form: TaskForm, status?: TaskStatus): { body: TaskWrite } | { error: string } {
  const title = form.title.trim();
  if (!title) return { error: "Give the task a title." };
  return {
    body: {
      title,
      detail: form.detail.trim() ? form.detail.trim() : null,
      due_on: form.due_on || null,
      priority: form.priority,
      status: status ?? form.status,
    },
  };
}

/**
 * Lightweight edit surface for one task.
 * Dismiss, Escape, and the backdrop close it without writing.
 */
export function TaskEditor({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const { refresh, system } = useHouse();
  const offerUndo = useUndo();
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  const titleRef = useRef<HTMLInputElement>(null);
  const focused = useRef(false);
  const headingId = useId();
  const titleFieldId = useId();
  const detailFieldId = useId();
  const dueFieldId = useId();
  const priorityFieldId = useId();
  const statusFieldId = useId();
  const [form, setForm] = useState<TaskForm | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getTask(taskId)
      .then((task) => {
        if (cancelled) return;
        setForm({
          title: task.title,
          detail: task.detail ?? "",
          due_on: task.due_on ?? "",
          priority: PRIORITIES.includes(task.priority) ? task.priority : "medium",
          status: STATUSES.includes(task.status) ? task.status : "todo",
        });
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  useEffect(() => {
    if (!form || focused.current) return;
    focused.current = true;
    titleRef.current?.focus();
  }, [form]);

  function update<K extends keyof TaskForm>(key: K, value: TaskForm[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  }

  async function save(status?: TaskStatus) {
    if (!form || busy) return;
    const next = bodyFrom(form, status);
    if ("error" in next) {
      setError(new Error(next.error));
      titleRef.current?.focus();
      return;
    }
    const previous = form.status;
    setBusy(true);
    setError(null);
    try {
      await updateTask(taskId, next.body);
      refresh();
      requestClose();
      if (status === "done" && previous !== "done") {
        offerUndo({
          message: "Marked done.",
          undo: async () => {
            await updateTask(taskId, { status: previous });
            refresh();
          },
        });
      }
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(false);
    }
  }

  const alreadyDone = form?.status === "done";

  async function removeTask() {
    if (!form || busy) return;
    const snapshot = bodyFrom(form);
    if ("error" in snapshot) return;
    setBusy(true);
    setError(null);
    try {
      await deleteTask(taskId);
      refresh();
      requestClose();
      offerUndo({
        message: "Task deleted.",
        undo: async () => {
          await createTask(snapshot.body);
          refresh();
        },
      });
    } catch (err: unknown) {
      setError(asError(err));
      setBusy(false);
    }
  }

  return (
    <dialog ref={dialogRef} className={cx(dialog, "task-dialog")} aria-labelledby={headingId}>
      <p className={kickerMuted}>Task</p>
      <h2 id={headingId} className={cx(heading, "mt-1")}>
        Edit task
      </h2>
      <p className={lede}>Change the title, detail, date, or status. Dismiss leaves it as it is.</p>
      {loadError && (
        <>
          <p className={errorText} role="alert">
            {loadError.message}
          </p>
          <div className={dialogActions}>
            <button type="button" className={ghost} onClick={requestClose}>
              Dismiss
            </button>
          </div>
        </>
      )}
      {!form && !loadError && <LoadingSkeleton label="Opening the task…" />}
      {form && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          {error && (
            <p className={errorText} role="alert">
              {error.message}
            </p>
          )}
          <label className={fieldStack} htmlFor={titleFieldId}>
            <span className={fieldLabel}>Title</span>
            <input
              ref={titleRef}
              id={titleFieldId}
              className={fieldInput}
              type="text"
              value={form.title}
              maxLength={200}
              required
              autoComplete="off"
              disabled={busy}
              onChange={(event) => update("title", event.target.value)}
            />
          </label>
          <label className={fieldStack} htmlFor={detailFieldId}>
            <span className={fieldLabel}>Detail</span>
            <textarea
              id={detailFieldId}
              className={cx(fieldInput, "min-h-[72px] resize-y py-2")}
              rows={3}
              value={form.detail}
              maxLength={4000}
              disabled={busy}
              onChange={(event) => update("detail", event.target.value)}
            />
          </label>
          <label className={fieldStack} htmlFor={dueFieldId}>
            <span className={fieldLabel}>Due</span>
            <input
              id={dueFieldId}
              className={cx(fieldInput, "font-mono tabular-nums")}
              type="date"
              value={form.due_on}
              disabled={busy}
              onChange={(event) => update("due_on", event.target.value)}
            />
            <span className={fieldHint}>Leave blank if there is no date.</span>
            <DatePassedNote dueOn={form.due_on} houseDate={system?.house_date} />
          </label>
          <div className="grid grid-cols-2 gap-4 max-[720px]:grid-cols-1">
            <label className={fieldStack} htmlFor={priorityFieldId}>
              <span className={fieldLabel}>Priority</span>
              <select
                id={priorityFieldId}
                className={fieldInput}
                value={form.priority}
                disabled={busy}
                onChange={(event) => update("priority", event.target.value as Priority)}
              >
                {PRIORITIES.map((value) => (
                  <option key={value} value={value}>
                    {PRIORITY_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className={fieldStack} htmlFor={statusFieldId}>
              <span className={fieldLabel}>Status</span>
              <select
                id={statusFieldId}
                className={fieldInput}
                value={form.status}
                disabled={busy}
                onChange={(event) => update("status", event.target.value as TaskStatus)}
              >
                {STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {STATUS_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {confirmingDelete ? (
            <div className={dialogActions}>
              <p className={lede}>Delete this task? You can undo it for a few seconds.</p>
              <button type="button" className={cx(ghost, "text-[var(--danger)]")} disabled={busy} onClick={() => void removeTask()}>
                Delete
              </button>
              <button type="button" className={ghost} disabled={busy} onClick={() => setConfirmingDelete(false)}>
                Keep
              </button>
            </div>
          ) : (
            <div className={dialogActions}>
              <button type="button" className={primary} disabled={busy || alreadyDone} onClick={() => void save("done")}>
                {alreadyDone ? "Done" : "Mark done"}
              </button>
              <button type="submit" className={ghost} disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </button>
              <button type="button" className={ghost} disabled={busy} onClick={() => setConfirmingDelete(true)}>
                Delete
              </button>
              <button type="button" className={ghost} disabled={busy} onClick={requestClose}>
                Dismiss
              </button>
            </div>
          )}
        </form>
      )}
    </dialog>
  );
}
