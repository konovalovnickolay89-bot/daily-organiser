import { useEffect, useState } from "react";
import { getHouseFacts } from "../api/system";
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

export function ThemeCard({ choice, onChoose }) {
  const { tick } = useHouse();
  const [facts, setFacts] = useState(null);
  const [error, setError] = useState(null);

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

  const rows = [
    ["Timezone", facts?.timezone ?? "…"],
    ["Assistant", assistantLabel(facts?.assistant)],
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
      <dl className="fact-list">
        {rows.map(([label, value]) => (
          <div key={label} className="fact-row">
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="lede mb-0">
        Diary is read-only and defaults to the primary calendar. A Wembley shift means Wembley Park, starting from
        home. None of that is connected yet.
      </p>
    </section>
  );
}
