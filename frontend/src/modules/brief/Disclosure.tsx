import { useCallback, useRef, type ReactNode } from "react";
import { cx } from "../../arrival/ui";

type DisclosureProps = {
  startOpen?: boolean;
  className?: string;
  summary: ReactNode;
  children: ReactNode;
};

/**
 * A disclosure that starts open or closed, then stays under the reader's control.
 * Passing `open` as a React prop would lock it on the next render.
 * The callback ref sets the initial state before paint, so it does not flash shut.
 */
export function Disclosure({ startOpen = false, className, summary, children }: DisclosureProps) {
  const startOpenRef = useRef(startOpen);
  const ref = useCallback((node: HTMLDetailsElement | null) => {
    if (node && startOpenRef.current) node.open = true;
  }, []);

  return (
    <details ref={ref} className={cx("group border-0 p-0", className)}>
      <summary className="block min-h-11 cursor-pointer list-none">{summary}</summary>
      {children}
    </details>
  );
}

export function Chevron() {
  return (
    <span className="text-xs text-[var(--muted)]" aria-hidden="true">
      <span className="group-open:hidden">▸</span>
      <span className="hidden group-open:inline">▾</span>
    </span>
  );
}
