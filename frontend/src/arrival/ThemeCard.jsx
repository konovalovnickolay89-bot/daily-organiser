import { useEffect, useState } from "react";
import { addCalendar, getHouseFacts, listCalendars, removeCalendar, setAssistantSwitch } from "../api/system";
import { useHouse } from "../house/HouseContext.jsx";

const OPTIONS = [
  ["auto", "House clock"],
  ["morning", "Morning"],
  ["evening", "Evening"],
];

function assistantLabel(value) {
  if (value === "on") return "On";
  if (value === "off") return "Off";
  return "…";
}

function configuredLabel(value) {
  if (value === "configured") return "Configured";
  if (value === "not configured") return "Not configured";
  return "…";
}

function CalendarEditor({ diary }) {
  const [calendars, setCalendars] = useState(null);
  const [name, setName] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (diary !== "configured") return undefined;
    let cancelled = false;
    listCalendars()
      .then((data) => {
        if (!cancelled) setCalendars(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [diary]);

  if (diary !== "configured") {
    return <p className="lede">Diary not connected — reconnect when a read-only calendar is set.</p>;
  }

  async function add(event) {
    event.preventDefault();
    const value = name.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      setCalendars(await addCalendar(value));
      setName("");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    setBusy(true);
    setError(null);
    try {
      setCalendars(await removeCalendar(id));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {calendars?.using_primary && <p className="lede">Using the primary calendar.</p>}
      {calendars?.items?.length > 0 && (
        <ul className="calendar-list">
          {calendars.items.map((item) => (
            <li key={item.id ?? item.name}>
              <span>{item.name}</span>
              {item.id && (
                <button type="button" className="ghost" disabled={busy} onClick={() => remove(item.id)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <form className="shop-add" onSubmit={add}>
        <label className="sr-only" htmlFor="calendar-name">
          Calendar name
        </label>
        <input
          id="calendar-name"
          type="text"
          value={name}
          maxLength={200}
          autoComplete="off"
          placeholder="Calendar name"
          disabled={busy}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className="ghost" disabled={busy || name.trim() === ""}>
          Add
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}

export function ThemeCard({ choice, onChoose }) {
  const { tick, refresh } = useHouse();
  const [facts, setFacts] = useState(null);
  const [error, setError] = useState(null);
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
      .catch((err) => {
        if (!cancelled) setError(err);
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
    } catch (err) {
      setError(err);
    } finally {
      setSwitching(false);
    }
  }

  const rows = [
    ["Timezone", facts?.timezone ?? "…"],
    ["Runs left today", facts ? String(facts.runs_left_today) : "…"],
    ["Diary", configuredLabel(facts?.diary)],
    ["Weather location", configuredLabel(facts?.weather_location)],
    ["TfL", configuredLabel(facts?.tfl)],
    ["Bantō", configuredLabel(facts?.banto)],
  ];

  return (
    <section className="card theme-card" aria-labelledby="settings-title" data-panel="settings">
      <h2 id="settings-title">Settings</h2>
      <p className="lede">
        Colour only. The greeting still comes from the house. Nothing on this card shows a location, a calendar id, or
        a token.
      </p>
      <p className="eyebrow">Theme</p>
      <div className="theme-choices" role="radiogroup" aria-label="Theme">
        {OPTIONS.map(([value, label]) => (
          <label key={value} className="theme-choice">
            <input
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
      <p className="eyebrow mt-6 mb-2">House</p>
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      <div className="switch-row">
        <label className="switch">
          <input
            type="checkbox"
            role="switch"
            checked={facts?.assistant_switch === "on"}
            disabled={!facts || switching}
            aria-label="Assistant"
            onChange={() => toggleAssistant()}
          />
          Assistant
        </label>
        <span className={facts?.assistant === "on" ? "is-success" : undefined}>{assistantLabel(facts?.assistant)}</span>
      </div>
      {facts?.assistant_switch === "on" && facts?.assistant === "off" && (
        <p className="lede">A key is not set, so the assistant stays off.</p>
      )}
      <dl className="fact-list">
        {rows.map(([label, value]) => (
          <div key={label} className="fact-row">
            <dt>{label}</dt>
            <dd className={value === "Configured" ? "is-success" : undefined}>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="eyebrow mt-6 mb-2">Diary</p>
      <CalendarEditor diary={facts?.diary} />
      <p className="lede mb-0">
        The diary is read-only. A Wembley shift means Wembley Park, starting from home. Shopping is names and ticks
        only.
      </p>
    </section>
  );
}
