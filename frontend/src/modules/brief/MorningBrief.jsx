import { useEffect, useState } from "react";
import { getMorningBrief } from "../../api/brief.js";
import { useHouse } from "../../house/HouseContext.jsx";
import { BriefSection } from "./BriefSection.jsx";
import { Disclosure } from "./Disclosure.jsx";

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
            <p className="empty">Opening the brief…</p>
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
          {(brief.sections ?? []).map((section) => (
            <BriefSection
              key={section.key}
              section={section}
              startOpen={OPEN_KEYS.has(section.key) && !section.placeholder}
            />
          ))}
        </Disclosure>
      )}
    </section>
  );
}
