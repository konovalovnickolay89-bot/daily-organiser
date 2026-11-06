/** The brief rule is the fallback after dated items. Other rules have no marker. */
export function catchUpFallbackMarker(rule?: string | null): string {
  return rule === "brief" ? "Fallback" : "";
}
