import { useEffect, useId, useRef, useState } from "react";
import { getTask, updateTask } from "../../api/tasks";
import { useHouse } from "../../house/HouseContext.jsx";
import { useHouseDialog } from "../../lib/dialog";
import { PRIORITY_LABELS, STATUS_LABELS } from "../../lib/labels";

const PRIORITIES = ["low", "medium", "high"];
const STATUSES = ["todo", "doing", "done"];

function bodyFrom(form, status) {
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
 * Save and Mark done use PATCH /tasks/{id}.
 */
export function TaskEditor({ taskId, onClose }) {
  const { refresh } = useHouse();
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  const titleRef = useRef(null);
  const focused = useRef(false);
  const headingId = useId();
  const titleFieldId = useId();
  const detailFieldId = useId();
  const dueFieldId = useId();
  const priorityFieldId = useId();
  const statusFieldId = useId();
  const [form, setForm] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      .catch((err) => {
        if (!cancelled) setLoadError(err);
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

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(status) {
    if (!form || busy) return;
    const next = bodyFrom(form, status);
    if (next.error) {
      setError(new Error(next.error));
      titleRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateTask(taskId, next.body);
      refresh();
      requestClose();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const alreadyDone = form?.status === "done";

  return (
    <dialog ref={dialogRef} className="task-dialog" aria-labelledby={headingId}>
      <p className="eyebrow">Task</p>
      <h2 id={headingId}>Edit task</h2>
      <p className="lede">Change the title, detail, date, or status. Dismiss leaves it as it is.</p>
      {loadError && (
        <>
          <p className="error" role="alert">
            {loadError.message}
          </p>
          <div className="actions task-actions">
            <button type="button" className="ghost" onClick={requestClose}>
              Dismiss
            </button>
          </div>
        </>
      )}
      {!form && !loadError && <p className="empty">Opening the task…</p>}
      {form && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          {error && (
            <p className="error" role="alert">
              {error.message}
            </p>
          )}
          <label className="field" htmlFor={titleFieldId}>
            <span>Title</span>
            <input
              ref={titleRef}
              id={titleFieldId}
              type="text"
              value={form.title}
              maxLength={200}
              required
              autoComplete="off"
              disabled={busy}
              onChange={(event) => update("title", event.target.value)}
            />
          </label>
          <label className="field" htmlFor={detailFieldId}>
            <span>Detail</span>
            <textarea
              id={detailFieldId}
              rows={3}
              value={form.detail}
              maxLength={4000}
              disabled={busy}
              onChange={(event) => update("detail", event.target.value)}
            />
          </label>
          <label className="field" htmlFor={dueFieldId}>
            <span>Due</span>
            <input
              id={dueFieldId}
              type="date"
              value={form.due_on}
              disabled={busy}
              onChange={(event) => update("due_on", event.target.value)}
            />
            <span className="field-hint">Leave blank if there is no date.</span>
          </label>
          <div className="field-row">
            <label className="field" htmlFor={priorityFieldId}>
              <span>Priority</span>
              <select
                id={priorityFieldId}
                value={form.priority}
                disabled={busy}
                onChange={(event) => update("priority", event.target.value)}
              >
                {PRIORITIES.map((value) => (
                  <option key={value} value={value}>
                    {PRIORITY_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field" htmlFor={statusFieldId}>
              <span>Status</span>
              <select
                id={statusFieldId}
                value={form.status}
                disabled={busy}
                onChange={(event) => update("status", event.target.value)}
              >
                {STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {STATUS_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="actions task-actions">
            <button
              type="button"
              className="primary"
              disabled={busy || alreadyDone}
              onClick={() => save("done")}
            >
              {alreadyDone ? "Done" : "Mark done"}
            </button>
            <button type="submit" className="ghost" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={requestClose}>
              Dismiss
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
