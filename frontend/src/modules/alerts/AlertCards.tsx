import { useEffect, useState } from "react";
import { dismissAlert, listAlerts, type HouseAlert } from "../../api/alerts";
import { SectionHeader } from "../../arrival/SectionHeader";
import { card, errorText, ghost } from "../../arrival/ui";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";

/**
 * Alert cards on the arrival screen. Dismiss hides that incident.
 * Nothing is sent.
 */
export function AlertCards() {
  const tick = useHouseTick();
  const [items, setItems] = useState<HouseAlert[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAlerts()
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
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

  async function dismiss(kind: string) {
    setBusy(kind);
    setError(null);
    try {
      const next = await dismissAlert(kind);
      setItems(next.items);
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(null);
    }
  }

  if (items.length === 0 && !error) return null;

  return (
    <div className="mt-8 grid gap-4" data-module="alerts">
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {items.map((item) => (
        <section key={item.kind} className={card} data-kind="alert" data-alert={item.kind} aria-labelledby={`alert-${item.kind}`}>
          <SectionHeader id={`alert-${item.kind}`} title={item.title} note={item.detail} />
          <button
            type="button"
            className={ghost}
            disabled={busy === item.kind}
            aria-label={`Dismiss ${item.title}`}
            onClick={() => void dismiss(item.kind)}
          >
            Dismiss
          </button>
        </section>
      ))}
    </div>
  );
}
