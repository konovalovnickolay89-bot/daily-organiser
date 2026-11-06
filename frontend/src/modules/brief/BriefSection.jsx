import { TaskRow } from "../tasks/TaskRow.jsx";
import { Disclosure } from "./Disclosure.jsx";

export function BriefSection({ section, startOpen = false, onOpenTask, onOpenCommitment }) {
  const tasksOpen = section.key === "tasks" && typeof onOpenTask === "function";
  const commitmentsOpen = section.key === "commitments" && typeof onOpenCommitment === "function";
  const openItem = tasksOpen ? onOpenTask : commitmentsOpen ? onOpenCommitment : null;
  const className = section.placeholder ? "brief-section is-placeholder" : "brief-section";

  return (
    <Disclosure
      className={className}
      startOpen={startOpen}
      summary={
        <>
          <span className="chevron" aria-hidden="true" />
          <span className="section-title">{section.title}</span>
          <span className="section-summary">
            {section.placeholder ? "Not connected" : section.summary}
          </span>
        </>
      }
    >
      {section.placeholder ? (
        <p className="placeholder-copy">{section.summary}</p>
      ) : section.items.length === 0 ? (
        <p className="empty">{section.summary}</p>
      ) : (
        <ul className="item-list">
          {section.items.map((item) =>
            openItem && item.id ? (
              <TaskRow
                key={item.id}
                title={item.title}
                meta={item.meta}
                detail={item.detail}
                onOpen={() => openItem(item.id)}
              />
            ) : (
              <li key={item.ref ?? item.id ?? item.title} className="item">
                <h3>{item.title}</h3>
                {item.meta && <p className="meta">{item.meta}</p>}
                {item.detail && <p>{item.detail}</p>}
              </li>
            ),
          )}
        </ul>
      )}
      {section.footnote && <p className="meta">{section.footnote}</p>}
    </Disclosure>
  );
}
