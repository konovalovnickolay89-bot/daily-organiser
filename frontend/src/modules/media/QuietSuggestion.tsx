import { useHouse } from "../../house/HouseContext";

/** Hidden unless SHOW_PLAYLIST_STUB is on. It still does not play anything. */
export function QuietSuggestion() {
  const { system } = useHouse();
  if (!system?.playlist_stub) return null;
  return (
    <aside
      className="quiet-suggestion serif mt-7 max-w-[18rem] text-left text-[0.95rem] font-normal italic leading-[1.35] text-cream-dim"
      data-module="quiet-media"
      aria-label="Later"
    >
      <p className="mb-1 font-sans text-[0.68rem] font-medium uppercase not-italic tracking-[0.16em] text-cream-dim">Later</p>
      <p className="m-0">A playlist is ready, when you want it.</p>
    </aside>
  );
}
