import { cx, fieldInput, heading, lede, primary } from "../../arrival/ui";
import { useView } from "../../arrival/view";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useAssistant } from "./AssistantContext";
import { AssistantResult } from "./AssistantResult";

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
  const { state, error, text, setText, sorting, enabled, paused, proposals, submit } = useAssistant();
  const inline = view !== "home";
  const restingEmpty = enabled && !paused && proposals.length === 0;

  return (
    <section
      className="assistant mt-7 min-w-0 max-w-full border-t border-[var(--line)] pt-[26px]"
      aria-labelledby="assistant-title"
      data-module="assistant"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="assistant-title" className={heading}>
          Proposed changes
        </h2>
        {enabled && !paused && inline && (
          <p className={cx("m-0 whitespace-nowrap text-[0.82rem] font-medium", proposals.length > 0 ? "font-semibold text-accent-ink" : "text-[var(--muted)]")}>
            {waitingLabel(proposals.length)}
          </p>
        )}
      </div>
      <p className={cx(lede, restingEmpty && inline && "text-[0.98rem] text-[var(--ink)]")}>
        {inline
          ? restingEmpty
            ? "Write a line for the log. Cards appear here."
            : "Apply makes that one change in the house log. Nothing is sent, bought, or booked."
          : "Write a line for the log. Cards appear on the right."}
      </p>
      {state === null && !error && <LoadingSkeleton label="Checking the assistant…" />}
      {state && !enabled && <p className="text-[0.9rem] text-[var(--muted)]">The assistant is off.</p>}
      {enabled && (
        <form
          className={cx(
            "mb-3 flex min-w-0 max-w-full gap-2",
            proposals.length > 0 && "max-[720px]:sticky max-[720px]:top-[60px] max-[720px]:z-[2] max-[720px]:-mx-2 max-[720px]:bg-card max-[720px]:p-2",
          )}
          onSubmit={(event) => void submit(event)}
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
            placeholder="A date, a bill, a thing to buy…"
            maxLength={1000}
            autoComplete="off"
            disabled={paused || sorting}
          />
          <button type="submit" className={cx(primary, "shrink-0")} disabled={paused || sorting || !text.trim()}>
            {sorting ? "Sorting…" : "Add"}
          </button>
        </form>
      )}
      {paused && <p className="mb-2.5 text-left text-[var(--muted)]">Paused. Nothing goes to the assistant.</p>}
      {inline && <AssistantResult heading={false} />}
    </section>
  );
}
