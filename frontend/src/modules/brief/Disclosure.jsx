import { useCallback, useRef } from "react";

/**
 * A disclosure that starts open or closed, then stays under the reader's control.
 * Passing `open` as a React prop would lock it on the next render.
 * The callback ref sets the initial state before paint, so it does not flash shut.
 */
export function Disclosure({ startOpen = false, className, summary, children }) {
  const startOpenRef = useRef(startOpen);
  const ref = useCallback((node) => {
    if (node && startOpenRef.current) {
      node.open = true;
    }
  }, []);

  return (
    <details ref={ref} className={className}>
      <summary>{summary}</summary>
      {children}
    </details>
  );
}
