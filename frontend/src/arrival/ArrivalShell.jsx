import { arrivalModules } from "./modules.js";
import { PresenceBar } from "../modules/presence/PresenceBar.jsx";

const KNOWN_SLOTS = new Set(["primary", "secondary", "corner"]);

function modulesIn(slot) {
  return arrivalModules.filter((mod) => mod.slot === slot);
}

function Pane({ slot, className, label }) {
  const modules = modulesIn(slot);
  if (modules.length === 0) return null;
  return (
    <section className={className} aria-label={label} data-slot={slot}>
      {modules.map((mod) => (
        <mod.Component key={mod.id} />
      ))}
    </section>
  );
}

function Corner() {
  const modules = modulesIn("corner");
  if (modules.length === 0) return null;
  return (
    <div className="corner" data-slot="corner">
      {modules.map((mod) => (
        <mod.Component key={mod.id} />
      ))}
    </div>
  );
}

/**
 * Arrival screen shell.
 * Presence stays here. Everything else is a module in arrival/modules.js.
 */
export function ArrivalShell() {
  const extras = arrivalModules.filter((mod) => !KNOWN_SLOTS.has(mod.slot));

  return (
    <main className="arrival">
      <PresenceBar />
      <div className="desk-wrap">
        <div className="desk">
          <Pane slot="primary" className="pane pane-primary" label="Daily needs" />
          <Pane slot="secondary" className="pane pane-secondary" label="Approvals, proposed changes, and today" />
          <Corner />
        </div>
        {extras.length > 0 && (
          <div className="extras">
            {extras.map((mod) => (
              <mod.Component key={mod.id} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
