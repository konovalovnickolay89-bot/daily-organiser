import type { BriefSection } from "../../api/brief";
import { errorText, heading, lede, meta, rowTitle } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";

export type CalendarOverview = {
  count: string;
  summary: string;
  urgent: string | null;
};

/** The brief uses this sentence for a missing secret and for a failed read. */
const NOT_CONNECTED = "Diary not connected — reconnect in Settings.";

/**
 * Compact row for the Home overview. The count is today's appointments.
 * A missing brief is an error. There is no separate diary health field.
 */
export function calendarOverview(section: BriefSection | null, error: Error | null): CalendarOverview {
  if (error) {
    return { count: "—", summary: "The diary could not be read.", urgent: error.message };
  }
  if (!section) {
    return { count: "—", summary: "The diary line is not in this brief.", urgent: null };
  }
  if (section.summary === NOT_CONNECTED) {
    return { count: "—", summary: section.summary, urgent: null };
  }
  return {
    count: String(section.items.length),
    summary: section.summary,
    urgent: section.items[0]?.title ?? null,
  };
}

/**
 * Today's titles and times from the brief. Read only.
 * The summary is the brief's own sentence, including an empty day or a failed read.
 */
export function CalendarDetail({ section, error }: { section: BriefSection | null; error: Error | null }) {
  return (
    <section
      aria-labelledby="calendar-title"
      data-panel="calendar"
      data-state={error ? "error" : section ? "ready" : "loading"}
    >
      <h2 id="calendar-title" className={heading}>
        Calendar
      </h2>
      <p className={lede}>Today only. Read only. This is not a calendar.</p>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {!section && !error && <LoadingSkeleton label="Checking today's diary…" />}
      {section && (
        <>
          <p className={lede} data-readout>
            {section.summary}
          </p>
          {section.items.length > 0 && (
            <ul className="m-0 list-none p-0">
              {section.items.map((item) => (
                <li key={item.ref ?? item.id ?? item.title} className="py-2">
                  <h3 className={rowTitle}>{item.title}</h3>
                  {item.meta && <p className={`${meta} mt-2 font-mono tabular-nums`}>{item.meta}</p>}
                </li>
              ))}
            </ul>
          )}
          {section.footnote && <p className={`${meta} mt-2`}>{section.footnote}</p>}
        </>
      )}
    </section>
  );
}
