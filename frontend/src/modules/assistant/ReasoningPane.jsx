import { useView } from "../../arrival/view";
import { AssistantResult } from "./AssistantResult.jsx";

/**
 * Right-hand column. A short working strip while Add runs, then the cards.
 * The next Add replaces the strip. This is not a chat.
 */
export function ReasoningPane() {
  const view = useView();
  if (view !== "home" && view !== "approvals") return null;
  return (
    <section className="module reasoning" aria-label="Assistant" data-module="reasoning">
      <AssistantResult />
    </section>
  );
}
