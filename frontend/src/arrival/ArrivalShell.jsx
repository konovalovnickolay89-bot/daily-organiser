import { useState } from "react";
import { useHouse } from "../house/HouseContext.jsx";
import { AssistantProvider } from "../modules/assistant/AssistantContext.jsx";
import { UndoProvider } from "../modules/tasks/UndoToast";
import { CatchUpStrip } from "../modules/catchup/CatchUpStrip.jsx";
import { PresenceBar } from "../modules/presence/PresenceBar.jsx";
import { Rail } from "./Rail.jsx";
import { ThemeCard } from "./ThemeCard.jsx";
import { arrivalModules } from "./modules.js";
import { useHouseTheme } from "./theme";
import { ViewProvider } from "./view";

const KNOWN = new Set(["brief", "today", "reasoning", "corner"]);

const PANELS = [
  { id: "brief", label: "Brief" },
  { id: "today", label: "Today" },
  { id: "reasoning", label: "Decisions" },
];

const MODULE_ORDER = {
  brief: ["morning-brief"],
  approvals: ["approvals"],
  today: ["today", "assistant"],
  corner: ["quiet-media"],
};

function modulesIn(panel) {
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
        <div className="shell" data-theme={theme} data-view={view}>
          <a className="skip-link" href="#main">
            Skip to content
          </a>
          <Rail view={view} onView={setView} />
          <main id="main" className="stage" tabIndex={-1}>
            <div className="stage-inner">
              <PresenceBar />
              <CatchUpStrip />
              <div className="cards">
                {PANELS.map((panel) => (
                  <section key={panel.id} className="card" data-panel={panel.id} aria-label={panel.label}>
                    {modulesIn(panel.id).map((mod) => (
                      <mod.Component key={mod.id} />
                    ))}
                  </section>
                ))}
              </div>
              {modulesIn("corner").map((mod) => (
                <mod.Component key={mod.id} />
              ))}
              {visibleExtras.length > 0 && (
                <div className="extras">
                  {visibleExtras.map((mod) => (
                    <section key={mod.id} className="card" data-panel={mod.panel}>
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
