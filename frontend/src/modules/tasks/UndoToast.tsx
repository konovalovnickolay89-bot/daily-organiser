import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

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
        <p className="toast" role="status">
          <span>{offer.message}</span>
          <button type="button" className="ghost" onClick={() => void undo()}>
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
