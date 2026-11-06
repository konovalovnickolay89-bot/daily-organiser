import { useEffect, useState } from "react";
import { approveRequest, listApprovals, skipRequest } from "../../api/approvals";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext.jsx";
import { MODE_LABELS } from "../../lib/labels";
import { orderedSteps, STEP_LABEL } from "./steps.js";
import { useAssistant } from "./AssistantContext.jsx";

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

function DecisionButtons({ busy, onApply, onDismiss }) {
  return (
    <div className="proposal-actions">
      <button type="button" className="primary" disabled={busy} onClick={onApply}>
        Apply
      </button>
      <button type="button" className="ghost not-now" disabled={busy} onClick={onDismiss}>
        Not now
      </button>
    </div>
  );
}

function DecisionList({ hideEmpty }) {
  const { tick, refresh } = useHouse();
  const { proposals, pendingId, decide, setNotice } = useAssistant();
  const [approvals, setApprovals] = useState(null);
  const [approvalError, setApprovalError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listApprovals("pending")
      .then((data) => {
        if (!cancelled) {
          setApprovals(data.items);
          setApprovalError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setApprovalError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  async function decideApproval(item, action) {
    setBusyId(item.id);
    setApprovalError(null);
    try {
      const result = action === "apply" ? await approveRequest(item.id) : await skipRequest(item.id);
      setNotice(result.effect?.summary || "Decision recorded. Nothing left the house.");
      refresh();
    } catch (err) {
      setApprovalError(err);
    } finally {
      setBusyId(null);
    }
  }

  const waiting = approvals ?? [];
  if (approvals === null && !approvalError) return null;
  if (proposals.length === 0 && waiting.length === 0) {
    if (hideEmpty) return null;
    return <p className="empty">Nothing is waiting.</p>;
  }
  return (
    <>
    {approvalError && (
      <p className="error" role="alert">
        {approvalError.message}
      </p>
    )}
    <ul className="proposal-list" data-surface="decisions">
      {waiting.map((item) => (
        <li key={`approval-${item.id}`} className="proposal-card" data-kind="approval">
          <p className="mode proposal-kicker">{MODE_LABELS[item.mode] ?? item.mode}</p>
          <h3 className="proposal-title">{item.title}</h3>
          {item.detail && <p className="proposal-reason">{item.detail}</p>}
          {item.mode === "execute" && (
            <p className="stub">Applying records the decision only. Nothing is sent.</p>
          )}
          <DecisionButtons
            busy={busyId === item.id}
            onApply={() => decideApproval(item, "apply")}
            onDismiss={() => decideApproval(item, "not-now")}
          />
        </li>
      ))}
      {proposals.map((proposal) => (
        <li key={`proposal-${proposal.id}`} className="proposal-card" data-origin={proposal.origin} data-kind="proposal">
          <p className="mode proposal-kicker">{proposal.label}</p>
          <h3 className="proposal-title">{proposal.summary}</h3>
          <p className="proposal-reason">{proposal.reason}</p>
          <DecisionButtons
            busy={pendingId === proposal.id}
            onApply={() => decide(proposal, "apply")}
            onDismiss={() => decide(proposal, "dismiss")}
          />
        </li>
      ))}
    </ul>
    </>
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
  // Approvals and proposals share this list, including when the assistant is off.
  const showCards = true;

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
              <h2 id="reasoning-proposals-title">Decisions</h2>
            </div>
          )}
          {heading && (
            <p className="lede">Apply or not now. Nothing is sent, bought, or booked.</p>
          )}
          {loading && <LoadingSkeleton label="Looking for decisions…" />}
          {reviewing && <p className="empty">Looking over the log…</p>}
          <DecisionList hideEmpty={sorting || reviewing || loading} />
        </div>
      )}
    </div>
  );
}
