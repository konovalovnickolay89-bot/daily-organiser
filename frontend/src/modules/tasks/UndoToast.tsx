import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { ghost } from "../../arrival/ui";

type Offer = {
  message: string;
  undo: () => Promise<void>;
};

type UndoContextValue = (offer: Offer) => void;

const UndoContext = createContext<UndoContextValue>(() => {});

const UNDO_MS = 8000;

export function UndoProvider({ children }: { children: ReactNode }) {
  const [offer, setOffer] = useState<Offer | null>(null);
  const timer = useRef<number | null>(null);

  const show = useCallback((next: Offer) => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    setOffer(next);
    timer.current = window.setTimeout(() => setOffer(null), UNDO_MS);
  }, []);

  async function undo() {
    if (!offer) return;
    const action = offer.undo;
    setOffer(null);
    if (timer.current !== null) window.clearTimeout(timer.current);
    await action();
  }

  return (
    <UndoContext.Provider value={show}>
      {children}
      {offer && (
        <p
          className="fixed bottom-6 left-1/2 z-40 m-0 flex max-w-[calc(100vw-32px)] -translate-x-1/2 items-center gap-4 rounded-house bg-card px-4 py-3 pl-[18px] text-ink-card shadow-[var(--card-shadow)]"
          role="status"
        >
          <span>{offer.message}</span>
          <button type="button" className={ghost} onClick={() => void undo()}>
            Undo
          </button>
        </p>
      )}
    </UndoContext.Provider>
  );
}

export function useUndo(): UndoContextValue {
  return useContext(UndoContext);
}
