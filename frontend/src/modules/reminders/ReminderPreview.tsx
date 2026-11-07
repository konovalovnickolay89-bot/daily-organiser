import { useEffect, useState } from "react";
import { getReminderPreview, prepareLocalReminders, type ReminderPreview as Preview, type ReminderSwitchName } from "../../api/agent";
import { setLocalReminders } from "../../api/system";
import type { HouseFacts } from "../../api/types";
import { cx, empty, errorText, kickerAccent, meta } from "../../arrival/ui";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";

const TYPES: { name: ReminderSwitchName; label: string; key: "reminder_overdue" | "reminder_stalled" | "reminder_upcoming" }[] = [
  { name: "overdue", label: "Overdue tasks", key: "reminder_overdue" },
  { name: "stalled", label: "Stalled items", key: "reminder_stalled" },
  { name: "upcoming", label: "Upcoming commitments", key: "reminder_upcoming" },
];

function withFacts(current: Preview, facts: HouseFacts): Preview {
  return {
    ...current,
    local_reminders: facts.local_reminders === "on" ? "on" : "off",
    reminder_overdue: facts.reminder_overdue === "on" ? "on" : "off",
    reminder_stalled: facts.reminder_stalled === "on" ? "on" : "off",
    reminder_upcoming: facts.reminder_upcoming === "on" ? "on" : "off",
    reminder_types_ready: facts.reminder_types_ready !== false,
  };
}

/**
 * Reads the reminder rules and, only when the house switch is on, asks for
 * one local card. The prepare call does not reach a provider. A type that is
 * off is not prepared, and a card already waiting is left in place.
 */
export function ReminderPreview() {
  const { tick, refresh } = useHouse();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [saving, setSaving] = useState(false);

  const enabled = preview?.local_reminders === "on";
  const typesReady = preview?.reminder_types_ready !== false;

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

  async function save(body: { enabled?: boolean; overdue?: boolean; stalled?: boolean; upcoming?: boolean }) {
    if (!preview || saving) return;
    setSaving(true);
    setError(null);
    try {
      const facts = await setLocalReminders(body);
      setPreview((current) => (current ? withFacts(current, facts) : current));
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
            onChange={() => void save({ enabled: !enabled })}
          />
          Local reminders
        </label>
      </div>
      <p className={cx(meta, "mt-2")}>
        {enabled
          ? "On. Saved for the house. One card may be prepared when its type is also on. Nothing is sent until Apply."
          : "Off. Saved for the house. Nothing is prepared, even when a type below is on. This switch does not call the assistant."}
      </p>
      <fieldset className="mt-4 grid gap-2 border-0 p-0" disabled={!preview || saving || !typesReady}>
        <legend className={cx(kickerAccent, "mb-1")}>Reminder types</legend>
        <p id="reminder-types-note" className={cx(meta, "m-0 mb-1")}>
          {typesReady
            ? "Each type stays off until you turn it on. The choice is kept when Local reminders is off."
            : "These types are off until the database update is applied. Nothing was turned on."}
        </p>
        {TYPES.map((item) => {
          const on = preview?.[item.key] === "on";
          return (
            <label key={item.name} className="flex min-h-11 cursor-pointer items-center gap-4 text-base text-[var(--ink)]">
              <input
                className="h-5 w-5 accent-accent"
                type="checkbox"
                role="switch"
                aria-label={item.label}
                checked={on}
                disabled={!preview || saving || !typesReady}
                onChange={() => {
                  if (!typesReady) return;
                  void save({ [item.name]: !on });
                }}
              />
              {item.label}
            </label>
          );
        })}
      </fieldset>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {preview && (
        <div className="mt-2 grid gap-2">
          <p className="m-0 text-base text-[var(--ink)]">{preview.note}</p>
          {preview.waiting_note && (
            <p className={cx(empty, "m-0")} role="status">
              {preview.waiting_note}
            </p>
          )}
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
                  <span className={cx(meta, "mt-1 block")}>
                    {item.reason}
                    {item.type_on ? "" : " This type is off."}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
