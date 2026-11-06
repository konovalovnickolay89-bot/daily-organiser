import { useEffect, useState } from "react";
import { listActivity, type ActivityLine } from "../../api/agent";
import { inset } from "../../arrival/ui";
import { useView } from "../../arrival/view";
import { useHouse } from "../../house/HouseContext";
import { AssistantResult } from "./AssistantResult";

/**
 * Right-hand column. A few recent log lines, then the working strip, then the cards.
 * The next Add replaces the strip. This is not a chat.
 */
export function ReasoningPane() {
  const view = useView();
  const { tick } = useHouse();
  const [lines, setLines] = useState<ActivityLine[]>([]);

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
    <section className="reasoning" aria-label="Assistant" data-module="reasoning">
      {lines.length > 0 && (
        <ol className={`${inset} mb-4 ml-0 mr-0 mt-0 grid list-none gap-2`} aria-label="Recent activity">
          {lines.map((line) => (
            <li key={line.id} className="text-sm leading-snug text-[var(--ink)]">
              {line.text}
            </li>
          ))}
        </ol>
      )}
      <AssistantResult />
    </section>
  );
}
