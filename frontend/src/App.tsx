import { ArrivalShell } from "./arrival/ArrivalShell";
import { HouseProvider } from "./house/HouseContext";

export function App() {
  return (
    <HouseProvider>
      <ArrivalShell />
    </HouseProvider>
  );
}
