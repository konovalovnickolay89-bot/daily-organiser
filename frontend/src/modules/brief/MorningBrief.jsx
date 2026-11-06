import { useEffect, useState } from "react";
import { getMorningBrief } from "../../api/brief";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext.jsx";
import { CommitmentEditor } from "../commitments/CommitmentEditor";
import { TaskEditor } from "../tasks/TaskEditor.jsx";
import { BriefSection } from "./BriefSection.jsx";
import { Disclosure } from "./Disclosure.jsx";
import { ShoppingList } from "./ShoppingList";

const OPEN_KEYS = new Set(["tasks", "commitments"]);

function foldLine(sections) {
  const tasks = sections.find((section) => section.key === "tasks");
  const commitments = sections.find((section) => section.key === "commitments");
  const parts = [];
  if (tasks?.summary) parts.push(tasks.summary);
  if (commitments && !commitments.placeholder) {
    parts.push(
      commitments.summary === "None open." ? "No open commitments" : `${commitments.summary} commitments`,
    );
  }
  return parts.join(" · ");
}

export function MorningBrief() {
  const { tick } = useHouse();
  const [brief, setBrief] = useState(null);
  const [error, setError] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [commitmentId, setCommitmentId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getMorningBrief()
      .then((data) => {
        if (!cancelled) {
          setBrief(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const line = brief ? foldLine(brief.sections ?? []) : "";

  return (
    <section className="module brief" aria-labelledby="brief-title" data-module="morning-brief">
      {!brief && (
        <>
          <h2 id="brief-title">Morning brief</h2>
          <p className="lede">Daily needs from the house log.</p>
          {error ? (
            <p className="error" role="alert">
              {error.message}
            </p>
          ) : (
            <LoadingSkeleton label="Opening the brief…" />
          )}
        </>
      )}
      {brief && (
        <Disclosure
          className="brief-fold"
          startOpen
          summary={
            <span className="brief-heading">
              <span className="chevron" aria-hidden="true" />
              <span className="brief-heading-text">
                <h2 id="brief-title">Morning brief</h2>
                {line && <span className="brief-fold-line">{line}</span>}
              </span>
            </span>
          }
        >
          <p className="lede">Daily needs from the house log.</p>
          {error && (
            <p className="error" role="alert">
              {error.message}
            </p>
          )}
          {brief.note && <p className="brief-note">{brief.note}</p>}
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
      {commitmentId && (
        <CommitmentEditor commitmentId={commitmentId} onClose={() => setCommitmentId(null)} />
      )}
    </section>
  );
}
