import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getSystem, pauseSystem, unpauseSystem } from "../api/system";

const HouseContext = createContext(null);

// The headline follows the server clock and the one-hour arrival window.
// Refresh the presence state on its own so a screen left open drops
// "Welcome home" when that hour ends, without reloading the desk.
const SYSTEM_REFRESH_MS = 60_000;

export function HouseProvider({ children }) {
  const [tick, setTick] = useState(0);
  const [system, setSystem] = useState(null);
  const [error, setError] = useState(null);
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
      .catch((err) => {
        if (!cancelled) setError(err);
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
        .catch((err) => {
          if (!busyRef.current) setError(err);
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
    } catch (err) {
      setError(err);
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

export function useHouse() {
  const value = useContext(HouseContext);
  if (!value) {
    throw new Error("useHouse must be used inside HouseProvider");
  }
  return value;
}
