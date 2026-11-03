import { useView } from "../../arrival/view.jsx";
import { useAssistant } from "./AssistantContext.jsx";
import { AssistantResult } from "./AssistantResult.jsx";

function waitingLabel(count) {
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
  const sectionClass = [
    "module",
    "assistant",
    enabled ? "is-on" : "",
    paused ? "is-paused" : "",
    proposals.length > 0 ? "has-cards" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={sectionClass} aria-labelledby="assistant-title" data-module="assistant">
      <div className="module-head">
        <h2 id="assistant-title">Proposed changes</h2>
        {enabled && !paused && inline && <p className="count">{waitingLabel(proposals.length)}</p>}
      </div>
      <p className={restingEmpty && inline ? "lede assistant-invite" : "lede"}>
        {inline
          ? restingEmpty
            ? "Write a line for the log. Cards appear here."
            : "Apply makes that one change in the house log. Nothing is sent, bought, or booked."
          : "Write a line for the log. Cards appear on the right."}
      </p>
      {state === null && !error && <p className="empty">Checking the assistant…</p>}
      {state && !enabled && <p className="empty">The assistant is off.</p>}
      {enabled && (
        <form className="feed-form" onSubmit={submit}>
          <label htmlFor="feed-text" className="sr-only">
            Add to the log
          </label>
          <input
            id="feed-text"
            type="text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="A date, a bill, a thing to buy…"
            maxLength={1000}
            autoComplete="off"
            disabled={paused || sorting}
          />
          <button type="submit" className="primary" disabled={paused || sorting || !text.trim()}>
            {sorting ? "Sorting…" : "Add"}
          </button>
        </form>
      )}
      {paused && <p className="status-note">Paused. Nothing goes to the assistant.</p>}
      {inline && <AssistantResult heading={false} />}
    </section>
  );
}
