import { createContext, useContext } from "react";

const ViewContext = createContext("home");

export function ViewProvider({ view, children }) {
  return <ViewContext.Provider value={view}>{children}</ViewContext.Provider>;
}

export function useView() {
  return useContext(ViewContext);
}
