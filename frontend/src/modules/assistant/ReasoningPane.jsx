import { useEffect, useState } from "react";
import { listActivity } from "../../api/agent";
import { useView } from "../../arrival/view";
import { useHouse } from "../../house/HouseContext.jsx";
import { AssistantResult } from "./AssistantResult.jsx";

/**
 * Right-hand column. A few recent log lines, then the working strip, then the cards.
 * The next Add replaces the strip. This is not a chat.
 */
export function ReasoningPane() {
  const view = useView();
  const { tick } = useHouse();
  const [lines, setLines] = useState([]);

  useEffect(() => {
    let cancelled = false;
    listActivity(5)
      .then((data) => {
        if (!cancelled) setLines(data.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setLines([]);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  if (view !== "home" && view !== "approvals") return null;
  return (
    <section className="module reasoning" aria-label="Assistant" data-module="reasoning">
      {lines.length > 0 && (
        <ol className="activity-lines" aria-label="Recent activity">
          {lines.map((line) => (
            <li key={line.id}>{line.text}</li>
          ))}
        </ol>
      )}
      <AssistantResult />
    </section>
  );
}
