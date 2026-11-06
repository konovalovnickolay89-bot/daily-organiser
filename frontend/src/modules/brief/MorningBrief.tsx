import { useEffect, useState } from "react";
import { getMorningBrief, type BriefSection as BriefSectionData, type MorningBrief as Brief } from "../../api/brief";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { cx, errorText, heading, lede, notice } from "../../arrival/ui";
import { CommitmentEditor } from "../commitments/CommitmentEditor";
import { TaskEditor } from "../tasks/TaskEditor";
import { BriefSection } from "./BriefSection";
import { Chevron, Disclosure } from "./Disclosure";
import { ShoppingList } from "./ShoppingList";

const OPEN_KEYS = new Set(["tasks", "commitments"]);

function foldLine(sections: BriefSectionData[]) {
  const tasks = sections.find((section) => section.key === "tasks");
  const commitments = sections.find((section) => section.key === "commitments");
  const parts = [];
  if (tasks?.summary) parts.push(tasks.summary);
  if (commitments && !commitments.placeholder) {
    parts.push(commitments.summary === "None open." ? "No open commitments" : `${commitments.summary} commitments`);
  }
  return parts.join(" · ");
}

export function MorningBrief() {
  const { tick } = useHouse();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [commitmentId, setCommitmentId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMorningBrief()
      .then((data) => {
        if (!cancelled) {
          setBrief(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const line = brief ? foldLine(brief.sections ?? []) : "";

  return (
    <section className="brief" aria-labelledby="brief-title" data-module="morning-brief">
      {!brief && (
        <>
          <h2 id="brief-title" className={heading}>
            Morning brief
          </h2>
          <p className={lede}>Daily needs from the house log.</p>
          {error ? (
            <p className={errorText} role="alert">
              {error.message}
            </p>
          ) : (
            <LoadingSkeleton label="Opening the brief…" />
          )}
        </>
      )}
      {brief && (
        <Disclosure
          startOpen
          summary={
            <span className="flex items-start gap-2">
              <Chevron />
              <span className="flex min-w-0 flex-col gap-2">
                <h2 id="brief-title" className={heading}>
                  Morning brief
                </h2>
                {line && (
                  <span className={cx("text-sm font-normal text-[var(--muted)] group-open:hidden", /\d/.test(line) && "font-mono tabular-nums")}>
                    {line}
                  </span>
                )}
              </span>
            </span>
          }
        >
          <p className={lede}>Daily needs from the house log.</p>
          {error && (
            <p className={errorText} role="alert">
              {error.message}
            </p>
          )}
          {brief.note && <p className={notice}>{brief.note}</p>}
          {(brief.sections ?? []).map((section) =>
            section.key === "shopping" ? (
              <ShoppingList key="shopping" section={section} />
            ) : (
              <BriefSection
                key={section.key}
                section={section}
                startOpen={OPEN_KEYS.has(section.key) && !section.placeholder}
                onOpenTask={section.key === "tasks" ? setTaskId : undefined}
                onOpenCommitment={section.key === "commitments" ? setCommitmentId : undefined}
              />
            ),
          )}
        </Disclosure>
      )}
      {taskId && <TaskEditor taskId={taskId} onClose={() => setTaskId(null)} />}
      {commitmentId && <CommitmentEditor commitmentId={commitmentId} onClose={() => setCommitmentId(null)} />}
    </section>
  );
}
