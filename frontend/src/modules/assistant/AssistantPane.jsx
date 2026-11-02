import { useCallback, useEffect, useRef, useState } from "react";
import { applyProposal, dismissProposal, feedAgent, getAgent, runReview } from "../../api/agent.js";
import { useHouse } from "../../house/HouseContext.jsx";

// GET /agent only reads. Re-read it every minute so a screen left open notices
// when the rules make a review due, the way the presence bar refreshes itself.
const AGENT_REFRESH_MS = 60_000;

function waitingLabel(count) {
  if (count === 0) return "None waiting";
  if (count === 1) return "1 waiting";
  return `${count} waiting`;
}

// Used only when the model sends cards but no words.
function addedLabel(count) {
  if (count === 0) return "Nothing to add.";
  if (count === 1) return "1 proposal added.";
  return `${count} proposals added.`;
}

/**
 * Proposed changes.
 *
 * One line in, cards out. The assistant only proposes. Apply makes that one
 * change in the house log; Not now dismisses it. There is no thread: the next
 * entry replaces the reply line.
 */
export function AssistantPane() {
  const { tick, refresh } = useHouse();
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [notice, setNotice] = useState("");
  const [sorting, setSorting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [pendingId, setPendingId] = useState(null);
  const reviewed = useRef(new Set());
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await getAgent();
      if (mounted.current) {
        setState(data);
        setError(null);
      }
    } catch (err) {
      if (mounted.current) setError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [tick, load]);

  useEffect(() => {
    const id = window.setInterval(load, AGENT_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [load]);

  // A review the rules say is due runs once per window from this screen.
  // The server checks again, so a second screen gets a quiet refusal.
  useEffect(() => {
    const due = state?.due;
    if (!due || !state.enabled || state.paused || sorting) return;
    if (reviewed.current.has(due.window_key)) return;
    reviewed.current.add(due.window_key);
    setReviewing(true);
    runReview(due)
      .then((result) => {
        if (mounted.current && result.reply) setReply(result.reply);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted.current) {
          setReviewing(false);
          load();
        }
      });
  }, [state, sorting, load]);

  async function submit(event) {
    event.preventDefault();
    const value = text.trim();
    if (!value || sorting) return;
    setSorting(true);
    setError(null);
    setNotice("");
    setReply("");
    try {
      const result = await feedAgent(value);
      if (!mounted.current) return;
      setText("");
      setReply(result.reply || addedLabel(result.proposals.length));
      await load();
    } catch (err) {
      if (mounted.current) setError(err);
    } finally {
      if (mounted.current) setSorting(false);
    }
  }

  async function decide(proposal, action) {
    setPendingId(proposal.id);
    setError(null);
    try {
      if (action === "apply") {
        const result = await applyProposal(proposal.id);
        setNotice(`Applied: ${result.applied.summary}`);
        refresh();
      } else {
        await dismissProposal(proposal.id);
        setNotice(
          proposal.origin === "proactive"
            ? "Not now. That item rests for 72 hours."
            : "Dismissed. Nothing changed.",
        );
        await load();
      }
    } catch (err) {
      setError(err);
      await load();
    } finally {
      setPendingId(null);
    }
  }

  const proposals = state?.proposals ?? [];
  const enabled = Boolean(state?.enabled);
  const paused = Boolean(state?.paused);
  const replyLine = reply || state?.last_reply?.text || "";
  // The invite is the empty state: it stays up with the input while nothing is proposed.
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
        {enabled && !paused && <p className="count">{waitingLabel(proposals.length)}</p>}
      </div>
      <p className={restingEmpty ? "lede assistant-invite" : "lede"}>
        {restingEmpty
          ? "Write a line for the log. Cards appear here."
          : "Apply makes that one change in the house log. Nothing is sent, bought, or booked."}
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
      {replyLine && !paused && (
        <p className="notice reply" role="status">
          {replyLine}
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {reviewing && <p className="empty">Looking over the log…</p>}
      {proposals.length > 0 && (
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
      )}
    </section>
  );
}
