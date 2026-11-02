import { useState } from "react";
import { useHouse } from "../house/HouseContext.jsx";
import { CatchUpStrip } from "../modules/catchup/CatchUpStrip.jsx";
import { PresenceBar } from "../modules/presence/PresenceBar.jsx";
import { Rail } from "./Rail.jsx";
import { ThemeCard } from "./ThemeCard.jsx";
import { arrivalModules } from "./modules.js";
import { useHouseTheme } from "./theme.js";

const KNOWN = new Set(["brief", "approvals", "today", "corner"]);

const PANELS = [
  { id: "brief", label: "Brief" },
  { id: "approvals", label: "Approvals" },
  { id: "today", label: "Today" },
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
    <div className="shell" data-theme={theme} data-view={view}>
      <Rail view={view} onView={setView} />
      <main className="stage">
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
  );
}
