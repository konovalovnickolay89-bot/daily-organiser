import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getSystem, pauseSystem, unpauseSystem } from "../api/system";
import type { SystemState } from "../api/types";
import { asError } from "../lib/errors";

type HouseValue = {
  tick: number;
  system: SystemState | null;
  error: Error | null;
  busy: boolean;
  refresh: () => void;
  togglePause: () => Promise<void>;
};

const HouseContext = createContext<HouseValue | null>(null);

const SYSTEM_REFRESH_MS = 60_000;

export function HouseProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0);
  const [system, setSystem] = useState<SystemState | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const refresh = useCallback(() => {
    setTick((value) => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getSystem()
      .then((data) => {
        if (!cancelled) {
          setSystem(data);
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

  useEffect(() => {
    const id = window.setInterval(() => {
      if (busyRef.current) return;
      getSystem()
        .then((data) => {
          if (busyRef.current) return;
          setSystem(data);
          setError(null);
        })
        .catch((err: unknown) => {
          if (!busyRef.current) setError(asError(err));
        });
    }, SYSTEM_REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);

  const togglePause = useCallback(async () => {
    if (!system || busy) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const next = system.paused ? await unpauseSystem() : await pauseSystem();
      setSystem(next);
      setError(null);
      setTick((value) => value + 1);
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [system, busy]);

  const value = useMemo(
    () => ({ tick, system, error, busy, refresh, togglePause }),
    [tick, system, error, busy, refresh, togglePause],
  );

  return <HouseContext.Provider value={value}>{children}</HouseContext.Provider>;
}

export function useHouse(): HouseValue {
  const value = useContext(HouseContext);
  if (!value) {
    throw new Error("useHouse must be used inside HouseProvider");
  }
  return value;
}
