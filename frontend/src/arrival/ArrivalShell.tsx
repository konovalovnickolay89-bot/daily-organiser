import { useState } from "react";
import { useHouse } from "../house/HouseContext";
import { AssistantProvider } from "../modules/assistant/AssistantContext";
import { AlertCards } from "../modules/alerts/AlertCards";
import { CatchUpStrip } from "../modules/catchup/CatchUpStrip";
import { PresenceBar } from "../modules/presence/PresenceBar";
import { UndoProvider } from "../modules/tasks/UndoToast";
import { Rail } from "./Rail";
import { ThemeCard } from "./ThemeCard";
import { HomeBoard } from "./HomeBoard";
import { arrivalModules } from "./modules";
import { card } from "./ui";
import { useHouseTheme } from "./theme";
import { ViewProvider } from "./view";

const KNOWN = new Set(["brief", "today", "reasoning", "corner"]);

const PANELS = [
  { id: "brief", label: "Brief", place: "col-start-1 row-start-1 max-[980px]:col-auto max-[980px]:row-auto" },
  { id: "today", label: "Today", place: "col-start-2 row-start-1 max-[980px]:col-auto max-[980px]:row-auto" },
  { id: "reasoning", label: "Decisions", place: "col-start-3 row-start-1 max-[980px]:col-auto max-[980px]:row-auto" },
];

const MODULE_ORDER: Record<string, string[]> = {
  brief: ["morning-brief"],
  approvals: ["approvals"],
  today: ["today", "assistant"],
  reasoning: ["reasoning"],
  corner: ["quiet-media"],
};

function modulesIn(panel: string) {
  const rank = new Map((MODULE_ORDER[panel] ?? []).map((id, index) => [id, index]));
  return arrivalModules
    .filter((mod) => mod.panel === panel)
    .sort((a, b) => (rank.get(a.id) ?? 50) - (rank.get(b.id) ?? 50));
}

/**
 * Arrival screen.
 * Icon rail, large greeting, then cream cards. Colour follows the house clock.
 */
export function ArrivalShell() {
  const { system } = useHouse();
  const { choice, theme, choose } = useHouseTheme(system?.greeting);
  const [view, setView] = useState("home");
  const extras = arrivalModules.filter((mod) => !KNOWN.has(mod.panel));
  const visibleExtras = extras.filter((mod) => view === "home" || view === mod.panel);

  return (
    <ViewProvider view={view}>
      <AssistantProvider>
        <UndoProvider>
          <div className="shell flex min-h-screen items-stretch bg-canvas max-[720px]:flex-col" data-theme={theme} data-view={view}>
            <a
              className="skip-link rounded-pill bg-card px-4 py-2 text-ink-card no-underline"
              href="#main"
            >
              Skip to content
            </a>
            <Rail view={view} onView={setView} />
            <main id="main" className="stage min-w-0 flex-1 outline-none" tabIndex={-1}>
              <div className="w-full min-w-0">
                <PresenceBar />
                <CatchUpStrip />
                <AlertCards />
                {view === "home" && <HomeBoard />}
                {view !== "home" && (
                <div className="cards mt-10 grid items-start gap-6 [grid-template-columns:minmax(0,1.14fr)_minmax(0,1fr)_minmax(256px,0.92fr)] max-[980px]:grid-cols-1">
                  {PANELS.map((panel) => (
                    <div key={panel.id} className={`${card} ${panel.place}`} data-panel={panel.id}>
                      {modulesIn(panel.id).map((mod) => (
                        <mod.Component key={mod.id} />
                      ))}
                    </div>
                  ))}
                </div>
                )}
                {modulesIn("corner").map((mod) => (
                  <mod.Component key={mod.id} />
                ))}
                {visibleExtras.length > 0 && (
                  <div className="mt-6 grid gap-6">
                    {visibleExtras.map((mod) => (
                      <section key={mod.id} className={card} data-panel={mod.panel}>
                        <mod.Component />
                      </section>
                    ))}
                  </div>
                )}
                <ThemeCard choice={choice} onChoose={choose} />
              </div>
            </main>
          </div>
        </UndoProvider>
      </AssistantProvider>
    </ViewProvider>
  );
}
