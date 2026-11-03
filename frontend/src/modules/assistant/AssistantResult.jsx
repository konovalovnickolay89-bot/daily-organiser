import { orderedSteps, STEP_LABEL } from "./steps.js";
import { useAssistant } from "./AssistantContext.jsx";

function waitingLabel(count) {
  if (count === 0) return "None waiting";
  if (count === 1) return "1 waiting";
  return `${count} waiting`;
}

function Ticker({ steps, enabled, paused, loading, known }) {
  if (loading) return <p className="ticker-line is-settled">Checking the assistant…</p>;
  if (!known) return null;
  if (!enabled) return <p className="ticker-line">The assistant is off.</p>;
  if (paused) {
    return (
      <div className="ticker" role="status">
        <p className="ticker-line">Paused.</p>
        <p className="ticker-line is-settled">Nothing goes to the assistant.</p>
      </div>
    );
  }
  if (steps.length === 0) {
    return (
      <p className="ticker-line" role="status">
        Quiet.
      </p>
    );
  }

  const ordered = orderedSteps(steps);
  const current = steps[steps.length - 1];
  return (
    <div className="ticker" role="status" aria-live="polite">
      {ordered.map((step) => {
        const active = step === current && step !== "done" && step !== "failed";
        const finished = current === "done";
        const className = [
          "ticker-line",
          step === "failed" ? "is-failed" : "",
          active ? "is-current" : "",
          !finished && !active && step !== "failed" && step !== current ? "is-settled" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <p key={step} className={className}>
            {STEP_LABEL[step]}
          </p>
        );
      })}
    </div>
  );
}

function ProposalList() {
  const { proposals, pendingId, decide } = useAssistant();
  if (proposals.length === 0) return null;
  return (
    <ul className="proposal-list">
      {proposals.map((proposal) => (
        <li key={proposal.id} className="proposal-card" data-origin={proposal.origin}>
          <p className="mode proposal-kicker">{proposal.label}</p>
          <h3 className="proposal-title">{proposal.summary}</h3>
          <p className="proposal-reason">{proposal.reason}</p>
          <div className="proposal-actions">
            <button
              type="button"
              className="primary"
              disabled={pendingId === proposal.id}
              onClick={() => decide(proposal, "apply")}
            >
              Apply
            </button>
            <button
              type="button"
              className="ghost not-now"
              disabled={pendingId === proposal.id}
              onClick={() => decide(proposal, "dismiss")}
            >
              Not now
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * Working strip, then the cards. The next Add replaces the strip.
 * There is no thread.
 */
export function AssistantResult({ heading = true }) {
  const { state, error, feedError, replyLine, notice, steps, proposals, reviewing, enabled, paused, sorting } =
    useAssistant();
  const loading = state === null && !error;
  const showCards = enabled && !paused;

  return (
    <div className="assistant-result">
      <Ticker steps={steps} enabled={enabled} paused={paused} loading={loading} known={state !== null} />
      {!paused && replyLine && (
        <p className="notice reply" role="status">
          {replyLine}
        </p>
      )}
      {!paused && notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {!paused && feedError && (
        <p className="error" role="alert">
          {feedError}
        </p>
      )}
      {!paused && error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {showCards && (
        <div className={heading ? "reasoning-proposals" : "inline-proposals"}>
          {heading && (
            <div className="module-head">
              <h2 id="reasoning-proposals-title">Proposed changes</h2>
              <p className={proposals.length > 0 ? "count is-waiting" : "count"}>{waitingLabel(proposals.length)}</p>
            </div>
          )}
          {heading && (
            <p className="lede">
              Apply makes that one change in the house log. Nothing is sent, bought, or booked.
            </p>
          )}
          {reviewing && <p className="empty">Looking over the log…</p>}
          {proposals.length === 0 && !sorting && !reviewing && (
            <p className="empty">Cards appear here.</p>
          )}
          <ProposalList />
        </div>
      )}
    </div>
  );
}
