import type { ReactNode } from "react";
import { empty } from "../arrival/ui";

/** The quiet line when a list has nothing to show. */
export function EmptyState({ children }: { children: ReactNode }) {
  return <p className={empty}>{children}</p>;
}
