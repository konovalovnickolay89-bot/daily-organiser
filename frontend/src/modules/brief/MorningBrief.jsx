import { useEffect, useState } from "react";
import { getMorningBrief } from "../../api/brief.js";
import { useHouse } from "../../house/HouseContext.jsx";

const OPEN_BY_DEFAULT = new Set(["tasks", "commitments"]);

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

  return (
    <section className="module brief" aria-labelledby="brief-title" data-module="morning-brief">
      <h2 id="brief-title">Morning brief</h2>
      <p className="lede">Daily needs, read from the house log.</p>
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {!brief && !error && <p className="empty">Opening the brief…</p>}
      {brief?.note && <p className="brief-note">{brief.note}</p>}
      {brief?.sections.map((section) => (
        <details key={section.key} defaultOpen={OPEN_BY_DEFAULT.has(section.key)}>
          <summary>
            <span className="chevron" aria-hidden="true" />
            <span className="section-title">{section.title}</span>
            <span className="section-summary">
              {section.placeholder ? "Not connected" : section.summary}
            </span>
          </summary>
          {section.placeholder ? (
            <p className="placeholder-copy">{section.summary}</p>
          ) : section.items.length === 0 ? (
            <p className="empty">Nothing in this section.</p>
          ) : (
            <ul className="item-list">
              {section.items.map((item) => (
                <li key={item.id ?? item.title} className="item">
                  <h3>{item.title}</h3>
                  {item.meta && <p className="meta">{item.meta}</p>}
                  {item.detail && <p>{item.detail}</p>}
                </li>
              ))}
            </ul>
          )}
        </details>
      ))}
    </section>
  );
}
