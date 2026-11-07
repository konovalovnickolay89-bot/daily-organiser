import { useState } from "react";
import { SectionHeader } from "../../arrival/SectionHeader";
import { cx, empty, fieldInput, primary } from "../../arrival/ui";
import { useView } from "../../arrival/view";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useAssistant } from "./AssistantContext";
import { AssistantResult } from "./AssistantResult";
import { VoiceControl } from "./VoiceControl";

function waitingLabel(count: number) {
  if (count === 0) return "None waiting";
  if (count === 1) return "1 waiting";
  return `${count} waiting`;
}

/**
 * The line in. On the home screen the cards and the working strip sit in the
 * right-hand column. On the Today view they stay here, under the form.
 */
export function AssistantPane() {
  const view = useView();
  const { state, error, text, setText, sorting, enabled, reachable, paused, proposals, submit } = useAssistant();
  const [voiceBusy, setVoiceBusy] = useState(false);
  const inline = view !== "home";
  const showForm = enabled && reachable;
  const restingEmpty = showForm && !paused && proposals.length === 0;

  return (
    <section className="assistant min-w-0 max-w-full" aria-labelledby="assistant-title" data-module="assistant">
      <SectionHeader
        id="assistant-title"
        title="Proposed changes"
        divided
        meta={showForm && !paused && inline ? waitingLabel(proposals.length) : undefined}
        metaClassName={proposals.length > 0 ? "font-semibold text-accent-ink" : undefined}
        note={
          inline
            ? restingEmpty
              ? "Write a line for the log. Cards appear here."
              : "Apply makes that one change in the house log. Nothing is sent, bought, or booked."
            : "Write a line for the log. Cards open under Decisions."
        }
      />
      {state === null && !error && <LoadingSkeleton label="Checking the assistant…" />}
      {state && !enabled && <p className={empty}>The assistant is off.</p>}
      {state && enabled && !reachable && <p className={empty}>The assistant is down.</p>}
      {showForm && (
        <form className="mb-4 mt-6 flex min-w-0 max-w-full flex-col gap-6" onSubmit={(event) => void submit(event)}>
          <div
            className={cx(
              "flex min-w-0 max-w-full gap-4",
              proposals.length > 0 &&
                "max-[720px]:sticky max-[720px]:top-16 max-[720px]:z-[2] max-[720px]:-mx-2 max-[720px]:bg-card max-[720px]:p-2",
            )}
          >
            <label htmlFor="feed-text" className="sr-only">
              Add to the log
            </label>
            <input
              id="feed-text"
              className={cx(fieldInput, "w-0 flex-1")}
              type="text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="A date, a bill, or remember …"
              maxLength={1000}
              autoComplete="off"
              disabled={paused || sorting}
            />
            <button type="submit" className={cx(primary, "shrink-0")} disabled={paused || sorting || voiceBusy || !text.trim()}>
              {sorting ? "Sorting…" : "Add"}
            </button>
          </div>
          <VoiceControl disabled={paused || sorting} onBusy={setVoiceBusy} onText={setText} />
        </form>
      )}
      {paused && <p className="mb-2 text-left text-sm text-[var(--muted)]">Paused. Nothing goes to the assistant.</p>}
      {inline && <AssistantResult heading={false} />}
    </section>
  );
}
