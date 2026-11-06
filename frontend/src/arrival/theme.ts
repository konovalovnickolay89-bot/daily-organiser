import { useCallback, useLayoutEffect, useState } from "react";

// Colour only. Greeting words stay on the server.
// The boot script in index.html mirrors the auto branch so the first paint matches.

const STORAGE_KEY = "organiser-theme";
const MORNING = new Set(["Good morning", "Good afternoon"]);
const EVENING = new Set(["Good evening", "Good night"]);

export type ThemeChoice = "auto" | "morning" | "evening";
export type ThemeName = "morning" | "evening";

const THEME_COLOR: Record<ThemeName, string> = {
  morning: "#1b1916",
  evening: "#050403",
};

export function houseHour(date = new Date()): number {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/London",
      hour: "numeric",
      hourCycle: "h23",
    }).formatToParts(date);
    const raw = parts.find((part) => part.type === "hour")?.value;
    const hour = Number(raw);
    if (!Number.isFinite(hour)) return 0;
    return ((hour % 24) + 24) % 24;
  } catch {
    return 0;
  }
}

export function themeForGreeting(greeting?: string | null, date = new Date()): ThemeName {
  if (greeting && MORNING.has(greeting)) return "morning";
  if (greeting && EVENING.has(greeting)) return "evening";
  const hour = houseHour(date);
  return hour >= 5 && hour < 17 ? "morning" : "evening";
}

export function readThemeChoice(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "auto" || value === "morning" || value === "evening") return value;
  } catch {
    /* storage unavailable */
  }
  return "auto";
}

export function writeThemeChoice(value: ThemeChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* storage unavailable */
  }
}

export function useHouseTheme(greeting?: string | null): {
  choice: ThemeChoice;
  theme: ThemeName;
  choose: (next: string) => void;
} {
  const [choice, setChoice] = useState(readThemeChoice);
  const theme = choice === "morning" || choice === "evening" ? choice : themeForGreeting(greeting);

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", THEME_COLOR[theme]);
  }, [theme]);

  const choose = useCallback((next: string) => {
    if (next !== "auto" && next !== "morning" && next !== "evening") return;
    writeThemeChoice(next);
    setChoice(next);
  }, []);

  return { choice, theme, choose };
}
