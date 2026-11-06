import { createContext, useContext, type ReactNode } from "react";

const ViewContext = createContext("home");

type ViewProviderProps = {
  view: string;
  children: ReactNode;
};

export function ViewProvider({ view, children }: ViewProviderProps) {
  return <ViewContext.Provider value={view}>{children}</ViewContext.Provider>;
}

export function useView(): string {
  return useContext(ViewContext);
}
