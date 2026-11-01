import { arrivalModules } from "./arrival/modules.js";
import { HouseProvider } from "./house/HouseContext.jsx";
import { PresenceBar } from "./modules/presence/PresenceBar.jsx";

const KNOWN_SLOTS = new Set(["primary", "secondary", "corner"]);

function Modules({ slot }) {
  return arrivalModules
    .filter((mod) => mod.slot === slot)
    .map((mod) => <mod.Component key={mod.id} />);
}

export function App() {
  const extras = arrivalModules.filter((mod) => !KNOWN_SLOTS.has(mod.slot));

  return (
    <HouseProvider>
      <main className="arrival">
        <PresenceBar />
        <div className="panes">
          <div className="pane pane-primary">
            <Modules slot="primary" />
          </div>
          <div className="pane pane-secondary">
            <Modules slot="secondary" />
          </div>
        </div>
        <Modules slot="corner" />
        {extras.length > 0 && (
          <div className="extras">
            {extras.map((mod) => (
              <mod.Component key={mod.id} />
            ))}
          </div>
        )}
      </main>
    </HouseProvider>
  );
}
