import { useEffect, useState } from "react";
import { getReminderPreview, type ReminderPreview as Preview } from "../../api/agent";
import { cx, empty, errorText, kickerAccent, meta } from "../../arrival/ui";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { previewShown, setPreviewShown } from "./previewStore";

/**
 * A reading of the reminder rules. It does not call the assistant.
 * The show/hide choice is proposed and stays on this browser.
 */
export function ReminderPreview() {
  const tick = useHouseTick();
  const [shown, setShown] = useState(previewShown);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!shown) return;
    let cancelled = false;
    getReminderPreview()
      .then((data) => {
        if (!cancelled) {
          setPreview(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick, shown]);

  function toggle() {
    const next = !shown;
    setShown(next);
    setPreviewShown(next);
  }

  return (
    <section className="mt-6 border-t border-[var(--line)] pt-4" aria-labelledby="reminder-preview-title" data-reminder-preview>
      <div className="flex min-h-11 flex-wrap items-center justify-between gap-2">
        <h3 id="reminder-preview-title" className={kickerAccent}>
          Reminder preview
        </h3>
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm text-[var(--muted)]">
          <input
            className="h-5 w-5 accent-accent"
            type="checkbox"
            checked={shown}
            onChange={toggle}
          />
          Show preview
        </label>
      </div>
      <p className={cx(meta, "mt-2")}>
        Proposed. Saved on this browser only. Hiding this does not start or stop the assistant.
      </p>
      {!shown && <p className={cx(empty, "mt-2")}>Preview hidden. Nothing was sent.</p>}
      {shown && error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {shown && preview && (
        <div className="mt-2 grid gap-2">
          <p className="m-0 text-base text-[var(--ink)]">{preview.note}</p>
          <p className={cx(meta, "m-0")}>
            Quiet hours {preview.quiet_hours}. Reminders left today {preview.proactive_left_today} of {preview.cap_proactive}. Runs left{" "}
            {preview.runs_left_today} of {preview.cap_runs}.
          </p>
          {preview.held_because && <p className={cx(empty, "m-0")}>{preview.held_because}</p>}
          {preview.due && <p className="m-0 text-base font-semibold text-[var(--ink)]">Due: {preview.due.label}</p>}
          {preview.candidates.length > 0 && (
            <ul className="m-0 grid list-none gap-2 p-0">
              {preview.candidates.map((item) => (
                <li key={`${item.rule}:${item.title}`} className="text-base text-[var(--ink)]">
                  <span className="font-semibold">{item.title}</span>
                  <span className={cx(meta, "mt-1 block")}>{item.reason}</span>
                </li>
              ))}
            </ul>
          )}
          {preview.calls_assistant !== false && (
            <p className={errorText} role="alert">
              This preview must not call the assistant.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
