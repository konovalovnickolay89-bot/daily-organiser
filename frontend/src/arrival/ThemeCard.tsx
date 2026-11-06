import { useEffect, useState, type FormEvent } from "react";
import { addCalendar, getHouseFacts, listCalendars, removeCalendar, setAssistantSwitch, type CalendarList } from "../api/system";
import type { HouseFacts } from "../api/types";
import { useHouse } from "../house/HouseContext";
import { asError } from "../lib/errors";
import { cx, card, errorText, fieldInput, ghost, heading, lede } from "./ui";

const OPTIONS = [
  ["auto", "House clock"],
  ["morning", "Morning"],
  ["evening", "Evening"],
] as const;

function assistantLabel(value?: string) {
  if (value === "on") return "On";
  if (value === "off") return "Off";
  return "…";
}

function configuredLabel(value?: string) {
  if (value === "configured") return "Configured";
  if (value === "not configured") return "Not configured";
  return "…";
}

function CalendarEditor({ diary }: { diary?: HouseFacts["diary"] }) {
  const [calendars, setCalendars] = useState<CalendarList | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (diary !== "configured") return undefined;
    let cancelled = false;
    listCalendars()
      .then((data) => {
        if (!cancelled) setCalendars(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [diary]);

  if (diary !== "configured") {
    return <p className={lede}>Diary not connected — reconnect when a read-only calendar is set.</p>;
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const value = name.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      setCalendars(await addCalendar(value));
      setName("");
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    setError(null);
    try {
      setCalendars(await removeCalendar(id));
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {calendars?.using_primary && <p className={lede}>Using the primary calendar.</p>}
      {calendars?.items && calendars.items.length > 0 && (
        <ul className="m-0 mt-2 list-none p-0">
          {calendars.items.map((item) => (
            <li key={item.id ?? item.name} className="flex min-h-11 items-center justify-between gap-3">
              <span>{item.name}</span>
              {item.id && (
                <button type="button" className={ghost} disabled={busy} onClick={() => void remove(item.id as string)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <form className="mt-3 flex gap-2" onSubmit={(event) => void add(event)}>
        <label className="sr-only" htmlFor="calendar-name">
          Calendar name
        </label>
        <input
          id="calendar-name"
          className={cx(fieldInput, "min-w-0 flex-1")}
          type="text"
          value={name}
          maxLength={200}
          autoComplete="off"
          placeholder="Calendar name"
          disabled={busy}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className={cx(ghost, "shrink-0")} disabled={busy || name.trim() === ""}>
          Add
        </button>
      </form>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}

export function ThemeCard({ choice, onChoose }: { choice: string; onChoose: (value: string) => void }) {
  const { tick, refresh } = useHouse();
  const [facts, setFacts] = useState<HouseFacts | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getHouseFacts()
      .then((data) => {
        if (!cancelled) {
          setFacts(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  async function toggleAssistant() {
    if (!facts || switching) return;
    setSwitching(true);
    setError(null);
    try {
      const next = await setAssistantSwitch(facts.assistant_switch !== "on");
      setFacts(next);
      refresh();
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setSwitching(false);
    }
  }

  const rows: Array<[string, string]> = [
    ["Timezone", facts?.timezone ?? "…"],
    ["Runs left today", facts ? String(facts.runs_left_today) : "…"],
    ["Diary", configuredLabel(facts?.diary)],
    ["Weather location", configuredLabel(facts?.weather_location)],
    ["TfL", configuredLabel(facts?.tfl)],
    ["Bantō", configuredLabel(facts?.banto)],
  ];

  return (
    <section className={cx(card, "theme-card mt-11 max-w-[34rem]")} aria-labelledby="settings-title" data-panel="settings">
      <h2 id="settings-title" className={heading}>
        Settings
      </h2>
      <p className={lede}>
        Colour only. The greeting still comes from the house. Nothing on this card shows a location, a calendar id, or a token.
      </p>
      <p className="m-0 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-[var(--muted)]">Theme</p>
      <div className="mt-1 flex flex-wrap gap-2.5" role="radiogroup" aria-label="Theme">
        {OPTIONS.map(([value, label]) => (
          <label
            key={value}
            className="relative inline-flex min-h-11 cursor-pointer items-center rounded-house border border-[var(--line)] px-4 text-[0.92rem] font-semibold has-[:checked]:border-transparent has-[:checked]:bg-accent has-[:checked]:text-[#1b140c] focus-within:outline focus-within:outline-2 focus-within:outline-offset-[3px] focus-within:outline-accent-ink"
          >
            <input
              className="absolute inset-0 m-0 cursor-pointer opacity-0"
              type="radio"
              name="organiser-theme"
              value={value}
              checked={choice === value}
              onChange={() => onChoose(value)}
            />
            {label}
          </label>
        ))}
      </div>
      <p className="mb-2 mt-6 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-[var(--muted)]">House</p>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      <div className="my-1 flex min-h-11 items-center justify-between gap-4">
        <label className="inline-flex min-h-11 min-w-11 cursor-pointer items-center gap-3">
          <input
            className="h-6 w-6 accent-accent"
            type="checkbox"
            role="switch"
            checked={facts?.assistant_switch === "on"}
            disabled={!facts || switching}
            aria-label="Assistant"
            onChange={() => void toggleAssistant()}
          />
          Assistant
        </label>
        <span className={facts?.assistant === "on" ? "font-semibold text-success" : undefined}>{assistantLabel(facts?.assistant)}</span>
      </div>
      {facts?.assistant_switch === "on" && facts?.assistant === "off" && (
        <p className={lede}>A key is not set, so the assistant stays off.</p>
      )}
      <dl className="m-0 mt-1 p-0">
        {rows.map(([label, value]) => (
          <div key={label} className="fact-row m-0 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-[var(--line)] py-2">
            <dt className="min-w-0 text-[0.95rem] font-normal text-[var(--muted)]">{label}</dt>
            <dd className={cx("m-0 min-w-0 text-right text-[0.95rem] font-semibold text-[var(--ink)]", value === "Configured" && "text-success")}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mb-2 mt-6 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-[var(--muted)]">Diary</p>
      <CalendarEditor diary={facts?.diary} />
      <p className="mb-0 mt-2 text-[0.95rem] leading-normal text-[var(--muted)]">
        The diary is read-only. A Wembley shift means Wembley Park, starting from home. Shopping is names and ticks only. The journey
        source is not connected.
      </p>
    </section>
  );
}
