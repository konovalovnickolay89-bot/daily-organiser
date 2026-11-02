import { useHouse } from "../../house/HouseContext.jsx";
import { formatHouseDate } from "../../lib/labels.js";

export function PresenceBar() {
  const { system, error, busy, togglePause } = useHouse();
  const paused = Boolean(system?.paused);
  const dateLabel = formatHouseDate(system?.house_date);
  const state = error ? "error" : system ? "ready" : "loading";

  let statusLine = "Checking the house…";
  if (error) statusLine = error.message;
  else if (system?.status_text) statusLine = system.status_text;

  let note = "";
  if (system && !error) {
    note = paused
      ? "Decisions can wait. Nothing will be prepared or sent."
      : "Nothing is being prepared or sent.";
  }

  return (
    <header
      className="presence"
      data-paused={paused ? "true" : "false"}
      data-state={state}
      data-greeting-reason={system?.greeting_reason ?? ""}
      aria-busy={busy ? "true" : "false"}
    >
      <p className="eyebrow">
        Home
        {dateLabel && <span className="eyebrow-date"> · {dateLabel}</span>}
      </p>
      <h1 className="greeting">{system?.greeting ?? ""}</h1>
      <div className="presence-control">
        <p className="status" role="status" aria-live="polite">
          <span className="status-mark" aria-hidden="true" />
          <span className="status-text">{statusLine}</span>
        </p>
        <button
          type="button"
          className="pause"
          aria-pressed={paused}
          aria-label={paused ? "Unpause the house" : "Pause the house"}
          disabled={!system || busy}
          onClick={togglePause}
        >
          {paused ? "Unpause" : "Pause"}
        </button>
      </div>
      {note && <p className="status-note">{note}</p>}
    </header>
  );
}
