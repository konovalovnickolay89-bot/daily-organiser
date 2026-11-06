import { useHouse } from "../../house/HouseContext";
import { formatHouseDate } from "../../lib/labels";
import { cx, pauseButton } from "../../arrival/ui";

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

  const statusColour = state === "error" ? "text-danger-canvas" : state === "loading" ? "text-cream-dim" : "text-cream";
  const markColour =
    state === "error" ? "bg-danger-canvas" : state === "loading" ? "bg-cream-dim" : "bg-accent shadow-[0_0_0_3px_var(--accent-soft)]";

  return (
    <header
      className="border-0 bg-transparent py-1 text-left"
      data-paused={paused ? "true" : "false"}
      data-state={state}
      data-greeting-reason={system?.greeting_reason ?? ""}
      aria-busy={busy ? "true" : "false"}
    >
      <p className="m-0 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-cream-dim">
        Home
        {dateLabel && <span className="text-[0.92rem] font-normal normal-case tracking-[0.01em]"> · {dateLabel}</span>}
      </p>
      <h1 className="greeting m-0 mt-2.5">{system?.greeting ?? ""}</h1>
      <div className="mt-[26px] flex max-w-full min-w-0 flex-row flex-wrap items-center justify-start gap-x-4 gap-y-3">
        <p className={cx("m-0 inline-flex min-w-0 items-center gap-2 text-[0.95rem] font-medium tracking-[-0.011em]", statusColour)} role="status" aria-live="polite">
          <span className={cx("h-[0.48rem] w-[0.48rem] shrink-0 rounded-full", markColour)} aria-hidden="true" />
          <span className="[overflow-wrap:anywhere]">{statusLine}</span>
        </p>
        <button
          type="button"
          className={pauseButton}
          aria-pressed={paused}
          aria-label={paused ? "Unpause the house" : "Pause the house"}
          disabled={!system || busy}
          onClick={() => void togglePause()}
        >
          {paused ? "Unpause" : "Pause"}
        </button>
      </div>
      {note && (
        <p className={cx("mt-3 max-w-[36rem] text-left text-[0.9rem]", paused ? "text-accent" : "text-cream-dim")}>{note}</p>
      )}
    </header>
  );
}
