import { useEffect, useId, useRef, useState } from "react";
import { getCommitment, updateCommitment } from "../../api/commitments";
import type { CommitmentStatus, CommitmentWrite } from "../../api/types";
import { cx, dialog, errorText, fieldInput, fieldLabel, ghost, heading, lede, primary } from "../../arrival/ui";
import { DatePassedNote } from "../../components/DatePassedNote";
import { useHouse } from "../../house/HouseContext";
import { useHouseDialog } from "../../lib/dialog";
import { COMMITMENT_STATUS_LABELS } from "../../lib/labels";

const STATUSES: CommitmentStatus[] = ["open", "kept", "dropped"];

type CommitmentForm = {
  title: string;
  detail: string;
  due_on: string;
  status: CommitmentStatus;
};

function bodyFrom(form: CommitmentForm, status?: CommitmentStatus): CommitmentWrite | null {
  const title = form.title.trim();
  if (!title) return null;
  return {
    title,
    detail: form.detail.trim() ? form.detail.trim() : null,
    due_on: form.due_on || null,
    status: status ?? form.status,
  };
}

function asError(err: unknown): Error {
  return err instanceof Error ? err : new Error("The house log could not be reached.");
}

type CommitmentEditorProps = {
  commitmentId: string;
  onClose: () => void;
};

/**
 * Edit one commitment. Dismiss, Escape, and the backdrop close it without writing.
 * Save and Mark kept use PATCH /commitments/{id}.
 */
export function CommitmentEditor({ commitmentId, onClose }: CommitmentEditorProps) {
  const { refresh, system } = useHouse();
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  const titleRef = useRef<HTMLInputElement>(null);
  const focused = useRef(false);
  const headingId = useId();
  const titleFieldId = useId();
  const detailFieldId = useId();
  const dueFieldId = useId();
  const statusFieldId = useId();
  const [form, setForm] = useState<CommitmentForm | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCommitment(commitmentId)
      .then((commitment) => {
        if (cancelled) return;
        setForm({
          title: commitment.title,
          detail: commitment.detail ?? "",
          due_on: commitment.due_on ?? "",
          status: STATUSES.includes(commitment.status) ? commitment.status : "open",
        });
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [commitmentId]);

  useEffect(() => {
    if (!form || focused.current) return;
    focused.current = true;
    titleRef.current?.focus();
  }, [form]);

  function update<Key extends keyof CommitmentForm>(key: Key, value: CommitmentForm[Key]) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  }

  async function save(status?: CommitmentStatus) {
    if (!form || busy) return;
    const next = bodyFrom(form, status);
    if (!next) {
      setError(new Error("Give the commitment a title."));
      titleRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateCommitment(commitmentId, next);
      refresh();
      requestClose();
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(false);
    }
  }

  const alreadyKept = form?.status === "kept";

  return (
    <dialog ref={dialogRef} className={cx(dialog, "house-dialog")} aria-labelledby={headingId}>
      <p className="m-0 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-[var(--muted)]">Commitment</p>
      <h2 id={headingId} className={cx(heading, "mt-1")}>
        Edit commitment
      </h2>
      <p className={lede}>Change the title, detail, date, or status. Dismiss leaves it as it is.</p>
      {loadError && (
        <>
          <p className={errorText} role="alert">
            {loadError.message}
          </p>
          <div className="mt-1 flex flex-wrap gap-2 border-t border-[var(--line)] pt-3.5">
            <button type="button" className={ghost} onClick={requestClose}>
              Dismiss
            </button>
          </div>
        </>
      )}
      {!form && !loadError && <p className="text-[0.9rem] text-[var(--muted)]">Opening the commitment…</p>}
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
          <label className="mb-3 flex flex-col gap-[5px]" htmlFor={titleFieldId}>
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
          <label className="mb-3 flex flex-col gap-[5px]" htmlFor={detailFieldId}>
            <span className={fieldLabel}>Detail</span>
            <textarea
              id={detailFieldId}
              className={cx(fieldInput, "min-h-[4.5rem] resize-y py-2")}
              rows={3}
              value={form.detail}
              maxLength={4000}
              disabled={busy}
              onChange={(event) => update("detail", event.target.value)}
            />
          </label>
          <label className="mb-3 flex flex-col gap-[5px]" htmlFor={dueFieldId}>
            <span className={fieldLabel}>Due</span>
            <input
              id={dueFieldId}
              className={fieldInput}
              type="date"
              value={form.due_on}
              disabled={busy}
              onChange={(event) => update("due_on", event.target.value)}
            />
            <span className="text-[0.78rem] font-normal normal-case tracking-normal text-[var(--muted)]">Leave blank if there is no date.</span>
            <DatePassedNote dueOn={form.due_on} houseDate={system?.house_date} />
          </label>
          <label className="mb-3 flex flex-col gap-[5px]" htmlFor={statusFieldId}>
            <span className={fieldLabel}>Status</span>
            <select
              id={statusFieldId}
              className={fieldInput}
              value={form.status}
              disabled={busy}
              onChange={(event) => update("status", event.target.value as CommitmentStatus)}
            >
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {COMMITMENT_STATUS_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-1 flex flex-wrap gap-2 border-t border-[var(--line)] pt-3.5">
            <button type="button" className={primary} disabled={busy || alreadyKept} onClick={() => void save("kept")}>
              {alreadyKept ? "Kept" : "Mark kept"}
            </button>
            <button type="submit" className={ghost} disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className={ghost} disabled={busy} onClick={requestClose}>
              Dismiss
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
