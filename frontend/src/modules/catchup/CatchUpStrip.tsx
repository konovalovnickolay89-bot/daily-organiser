import { useCallback, useEffect, useState } from "react";
import { applyCatchUp, dismissCatchUp, recordLook } from "../../api/catchup";
import type { CatchUpCard, CatchUpState } from "../../api/types";
import { cx, ghost, heading, lede, notice, primary } from "../../arrival/ui";
import { useHouse } from "../../house/HouseContext";
import { catchUpFallbackMarker } from "../../lib/catchup";
import { asError } from "../../lib/errors";

const LOOK_MS = 60_000;

function waitingLabel(count: number) {
  if (count === 1) return "1 to look at";
  return `${count} to look at`;
}

type CatchUpCardViewProps = {
  item: CatchUpCard;
  busy: boolean;
  onApply: () => void;
  onDismiss: () => void;
};

export function CatchUpCardView({ item, busy, onApply, onDismiss }: CatchUpCardViewProps) {
  const marker = catchUpFallbackMarker(item.rule);
  return (
    <li className="m-0 rounded-house border border-[var(--line)] bg-card px-3.5 pb-3 pt-3.5" data-rule={item.rule}>
      <p className="mb-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-ink">
        {item.label}
        {marker && (
          <span className="ml-2" data-marker="fallback">
            {marker}
          </span>
        )}
      </p>
      <h3 className="m-0 text-[0.98rem] font-semibold text-[var(--ink)] [overflow-wrap:anywhere]">{item.summary}</h3>
      <p className="mt-0.5 text-[0.9rem] text-[var(--muted)]">{item.reason}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={primary} disabled={busy} onClick={onApply}>
          Apply
        </button>
        <button type="button" className={ghost} disabled={busy} onClick={onDismiss}>
          Not now
        </button>
      </div>
    </li>
  );
}

/**
 * Catch up.
 * One strip after a gap. Each card is a note waiting for Apply. Not now rests that item.
 */
export function CatchUpStrip() {
  const { tick, refresh, system } = useHouse();
  const [state, setState] = useState<CatchUpState | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [message, setMessage] = useState("");
  const [pendingId, setPendingId] = useState<string | null>(null);

  const look = useCallback(async () => {
    if (document.visibilityState === "hidden") return null;
    try {
      const data = await recordLook();
      setState(data);
      setError(null);
      return data;
    } catch (err: unknown) {
      setError(asError(err));
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (document.visibilityState === "hidden") return;
      try {
        const data = await recordLook();
        if (!cancelled) {
          setState(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) setError(asError(err));
      }
    }
    void run();
    const id = window.setInterval(() => void run(), LOOK_MS);
    document.addEventListener("visibilitychange", run);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", run);
    };
  }, [tick]);

  async function decide(item: CatchUpCard, action: "apply" | "dismiss") {
    setPendingId(item.id);
    setError(null);
    try {
      if (action === "apply") {
        const result = await applyCatchUp(item.id);
        setMessage(`Applied: ${result.applied.summary}`);
        refresh();
      } else {
        await dismissCatchUp(item.id);
        setMessage("Not now. That rests for 72 hours.");
        await look();
      }
    } catch (err: unknown) {
      setError(asError(err));
      await look();
    } finally {
      setPendingId(null);
    }
  }

  const items = state?.items ?? [];
  if (system?.paused || state?.paused || state?.quiet) return null;
  if (!items.length && !message) return null;

  return (
    <section className="catch-up paper mt-10 rounded-house bg-card px-[30px] pb-[22px] pt-7 text-[var(--ink)] shadow-[var(--card-shadow)] max-[720px]:px-[18px] max-[720px]:pb-4 max-[720px]:pt-[22px]" aria-labelledby="catch-up-title" data-module="catch-up">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="catch-up-title" className={cx(heading, "text-[1.45rem]")}>
          Catch up
        </h2>
        {items.length > 0 && <p className="m-0 whitespace-nowrap text-[0.82rem] font-medium text-[var(--muted)]">{waitingLabel(items.length)}</p>}
      </div>
      <p className={lede}>A few things that need a look. Apply adds one note. Nothing is sent.</p>
      {message && (
        <p className={notice} role="status">
          {message}
        </p>
      )}
      {error && items.length > 0 && (
        <p className="mb-3 text-[var(--danger)]" role="alert">
          {error.message}
        </p>
      )}
      {items.length > 0 && (
        <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3 p-0">
          {items.map((item) => (
            <CatchUpCardView
              key={item.id}
              item={item}
              busy={pendingId === item.id}
              onApply={() => void decide(item, "apply")}
              onDismiss={() => void decide(item, "dismiss")}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
