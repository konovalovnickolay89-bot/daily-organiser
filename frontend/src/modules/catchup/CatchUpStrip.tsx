import { useCallback, useEffect, useState } from "react";
import { applyCatchUp, dismissCatchUp, recordLook } from "../../api/catchup";
import type { CatchUpCard, CatchUpState } from "../../api/types";
import { SectionHeader } from "../../arrival/SectionHeader";
import { actions, card, cx, errorText, ghost, inset, kickerAccent, meta, notice, primary, subheading } from "../../arrival/ui";
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
  const marker = item.fallback_used ? "Fallback used" : catchUpFallbackMarker(item.rule);
  return (
    <li className={cx(inset, "m-0")} data-rule={item.rule}>
      <p className={cx(kickerAccent, "mb-2")}>
        {item.label}
        {marker && (
          <span className="ml-2 font-mono normal-case tracking-normal" data-marker="fallback">
            {marker}
          </span>
        )}
      </p>
      <h3 className={subheading}>{item.summary}</h3>
      <p className={cx(meta, "mt-2")}>{item.reason}</p>
      <div className={actions}>
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
    <section className={cx(card, "catch-up mt-10")} aria-labelledby="catch-up-title" data-module="catch-up">
      <SectionHeader
        id="catch-up-title"
        title="Catch up"
        note="A few things that need a look. Apply adds one note. Nothing is sent."
        meta={items.length > 0 ? waitingLabel(items.length) : undefined}
      />
      {message && (
        <p className={notice} role="status">
          {message}
        </p>
      )}
      {error && items.length > 0 && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {items.length > 0 && (
        <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(224px,1fr))] gap-4 p-0">
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
