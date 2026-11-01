import { ArrivalShell } from "./arrival/ArrivalShell.jsx";
import { HouseProvider } from "./house/HouseContext.jsx";

export function App() {
  return (
    <HouseProvider>
      <ArrivalShell />
    </HouseProvider>
  );
}
