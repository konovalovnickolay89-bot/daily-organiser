import { useCallback, useEffect, useState } from "react";
import { applyCatchUp, dismissCatchUp, recordLook } from "../../api/catchup";
import { useHouse } from "../../house/HouseContext.jsx";

// A screen left open keeps its look fresh, so a gap is time away from the page.
const LOOK_MS = 60_000;

function waitingLabel(count) {
  if (count === 1) return "1 to look at";
  return `${count} to look at`;
}

/**
 * Catch up.
 *
 * One strip after a gap. Each card is a note waiting for Apply. Not now rests
 * that item. There is no thread.
 */
export function CatchUpStrip() {
  const { tick, refresh, system } = useHouse();
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [pendingId, setPendingId] = useState(null);

  const look = useCallback(async () => {
    if (document.visibilityState === "hidden") return null;
    try {
      const data = await recordLook();
      setState(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err);
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
      } catch (err) {
        if (!cancelled) setError(err);
      }
    }
    run();
    const id = window.setInterval(run, LOOK_MS);
    document.addEventListener("visibilitychange", run);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", run);
    };
  }, [tick]);

  async function decide(item, action) {
    setPendingId(item.id);
    setError(null);
    try {
      if (action === "apply") {
        const result = await applyCatchUp(item.id);
        setNotice(`Applied: ${result.applied.summary}`);
        refresh();
      } else {
        await dismissCatchUp(item.id);
        setNotice("Not now. That rests for 72 hours.");
        await look();
      }
    } catch (err) {
      setError(err);
      await look();
    } finally {
      setPendingId(null);
    }
  }

  const items = state?.items ?? [];
  // Nothing on the strip while the house is paused, or during quiet hours.
  if (system?.paused || state?.paused || state?.quiet) return null;
  if (!items.length && !notice) return null;

  return (
    <section className="catch-up" aria-labelledby="catch-up-title" data-module="catch-up">
      <div className="module-head">
        <h2 id="catch-up-title">Catch up</h2>
        {items.length > 0 && <p className="count">{waitingLabel(items.length)}</p>}
      </div>
      <p className="lede">A few things that need a look. Apply adds one note. Nothing is sent.</p>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && items.length > 0 && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {items.length > 0 && (
        <ul className="approval-list catch-up-list">
          {items.map((item) => (
            <li key={item.id} className="approval proposal" data-rule={item.rule}>
              <p className="mode">{item.label}</p>
              <h3>{item.summary}</h3>
              <p>{item.reason}</p>
              {item.fallback_used && <p className="fallback-mark">Fallback used</p>}
              <div className="actions">
                <button
                  type="button"
                  className="primary"
                  disabled={pendingId === item.id}
                  onClick={() => decide(item, "apply")}
                >
                  Apply
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={pendingId === item.id}
                  onClick={() => decide(item, "dismiss")}
                >
                  Not now
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
