import { useHouse } from "../../house/HouseContext.jsx";

export function PresenceBar() {
  const { system, error, busy, togglePause } = useHouse();
  const paused = Boolean(system?.paused);

  return (
    <header className="presence" data-paused={paused ? "true" : "false"}>
      <p className="eyebrow">Home</p>
      <h1>Welcome home</h1>
      <p className="status" role="status">
        {error ? error.message : (system?.status_text ?? "Checking the house…")}
      </p>
      {paused && (
        <p className="status-note">Decisions can wait. Nothing will be prepared or sent.</p>
      )}
      <button
        type="button"
        className="pause"
        aria-pressed={paused}
        disabled={!system || busy}
        onClick={togglePause}
      >
        {paused ? "Resume" : "Pause"}
      </button>
    </header>
  );
}
