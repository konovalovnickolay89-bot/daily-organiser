import { useEffect, useState } from "react";
import { getReminderPreview, prepareLocalReminders, type ReminderPreview as Preview } from "../../api/agent";
import { setLocalReminders } from "../../api/system";
import { cx, empty, errorText, kickerAccent, meta } from "../../arrival/ui";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";

/**
 * Reads the reminder rules and, only when the house switch is on, asks for
 * one local card. The prepare call does not reach a provider.
 */
export function ReminderPreview() {
  const { tick, refresh } = useHouse();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [saving, setSaving] = useState(false);

  const enabled = preview?.local_reminders === "on";

  useEffect(() => {
    let cancelled = false;
    getReminderPreview()
      .then(async (data) => {
        if (cancelled) return;
        setPreview(data);
        setError(null);
        if (data.local_reminders !== "on") return;
        const prepared = await prepareLocalReminders();
        if (cancelled) return;
        if (prepared.calls_assistant) {
          setError(new Error("Local reminders must not call the assistant."));
          return;
        }
        if (prepared.prepared > 0) refresh();
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick, refresh]);

  async function toggle() {
    if (!preview || saving) return;
    setSaving(true);
    setError(null);
    try {
      const facts = await setLocalReminders(!enabled);
      setPreview((current) => (current ? { ...current, local_reminders: facts.local_reminders === "on" ? "on" : "off" } : current));
      refresh();
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setSaving(false);
    }
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
            role="switch"
            aria-label="Local reminders"
            checked={enabled}
            disabled={!preview || saving}
            onChange={() => void toggle()}
          />
          Local reminders
        </label>
      </div>
      <p className={cx(meta, "mt-2")}>
        {enabled
          ? "On. Saved for the house. One card may be prepared from the rules. Nothing is sent until Apply."
          : "Off. Saved for the house. Nothing is prepared, and this switch does not call the assistant."}
      </p>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {preview && (
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
        </div>
      )}
    </section>
  );
}
