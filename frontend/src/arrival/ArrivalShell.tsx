import { useState } from "react";
import { useHouse } from "../house/HouseContext";
import { AssistantProvider } from "../modules/assistant/AssistantContext";
import { AlertCards } from "../modules/alerts/AlertCards";
import { CatchUpStrip } from "../modules/catchup/CatchUpStrip";
import { PresenceBar } from "../modules/presence/PresenceBar";
import { UndoProvider } from "../modules/tasks/UndoToast";
import { Rail } from "./Rail";
import { ThemeCard } from "./ThemeCard";
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
  reasoning: ["reasoning", "x-cards"],
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
              className="skip-link rounded-house bg-card px-3.5 py-2.5 text-ink-card no-underline"
              href="#main"
            >
              Skip to content
            </a>
            <Rail view={view} onView={setView} />
            <main
              id="main"
              className="stage min-w-0 flex-1 pb-[72px] pl-8 pr-10 pt-10 outline-none min-[1100px]:pb-24 min-[1100px]:pl-12 min-[1100px]:pr-[72px] min-[1100px]:pt-[52px] max-[720px]:px-[18px] max-[720px]:pb-12 max-[720px]:pt-7"
              tabIndex={-1}
            >
              <div className="max-w-[1280px]">
                <PresenceBar />
                <CatchUpStrip />
                <AlertCards />
                <div className="cards mt-11 grid items-start gap-[22px] [grid-template-columns:minmax(0,1.14fr)_minmax(0,1fr)_minmax(250px,0.92fr)] max-[980px]:grid-cols-1">
                  {PANELS.map((panel) => (
                    <div key={panel.id} className={`${card} ${panel.place}`} data-panel={panel.id}>
                      {modulesIn(panel.id).map((mod) => (
                        <mod.Component key={mod.id} />
                      ))}
                    </div>
                  ))}
                </div>
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
