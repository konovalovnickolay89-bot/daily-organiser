import { TaskRow } from "../tasks/TaskRow.jsx";
import { Disclosure } from "./Disclosure.jsx";

export function BriefSection({ section, startOpen = false, onOpenTask }) {
  const tasksOpen = section.key === "tasks" && typeof onOpenTask === "function";
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
        <p className="empty">Nothing in this section.</p>
      ) : (
        <ul className="item-list">
          {section.items.map((item) =>
            tasksOpen && item.id ? (
              <TaskRow
                key={item.id}
                title={item.title}
                meta={item.meta}
                detail={item.detail}
                onOpen={() => onOpenTask(item.id)}
              />
            ) : (
              <li key={item.id ?? item.title} className="item">
                <h3>{item.title}</h3>
                {item.meta && <p className="meta">{item.meta}</p>}
                {item.detail && <p>{item.detail}</p>}
              </li>
            ),
          )}
        </ul>
      )}
    </Disclosure>
  );
}
