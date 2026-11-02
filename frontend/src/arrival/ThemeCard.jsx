const OPTIONS = [
  ["auto", "House clock"],
  ["morning", "Morning"],
  ["evening", "Evening"],
];

export function ThemeCard({ choice, onChoose }) {
  return (
    <section className="card theme-card" aria-labelledby="theme-title" data-panel="settings">
      <h2 id="theme-title">Theme</h2>
      <p className="lede">Colour only. The greeting still comes from the house.</p>
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
    </section>
  );
}
