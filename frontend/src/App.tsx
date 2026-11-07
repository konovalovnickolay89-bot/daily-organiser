import { ArrivalShell } from "./arrival/ArrivalShell";
import { layoutPreviewQuery, LayoutPreview } from "./arrival/LayoutPreview";
import { HouseProvider } from "./house/HouseContext";

export function App() {
  if (import.meta.env.DEV && layoutPreviewQuery()) return <LayoutPreview />;
  return (
    <HouseProvider>
      <ArrivalShell />
    </HouseProvider>
  );
}
