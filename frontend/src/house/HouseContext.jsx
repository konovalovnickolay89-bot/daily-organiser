import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getSystem, pauseSystem, unpauseSystem } from "../api/system.js";

const HouseContext = createContext(null);

export function HouseProvider({ children }) {
  const [tick, setTick] = useState(0);
  const [system, setSystem] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const togglePause = useCallback(async () => {
    if (!system || busy) return;
    setBusy(true);
    try {
      const next = system.paused ? await unpauseSystem() : await pauseSystem();
      setSystem(next);
      setError(null);
      setTick((value) => value + 1);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }, [system, busy]);

  const value = useMemo(
    () => ({ tick, system, error, busy, refresh, togglePause }),
    [tick, system, error, busy, refresh, togglePause],
  );

  return <HouseContext.Provider value={value}>{children}</HouseContext.Provider>;
}

export function useHouse() {
  const value = useContext(HouseContext);
  if (!value) {
    throw new Error("useHouse must be used inside HouseProvider");
  }
  return value;
}
