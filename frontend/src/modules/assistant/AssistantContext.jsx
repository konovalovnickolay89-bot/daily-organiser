import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { applyProposal, dismissProposal, feedAgent, getAgent, runReview } from "../../api/agent";
import { useHouse } from "../../house/HouseContext.jsx";
import { noteStep } from "./steps.js";

// GET /agent only reads. Re-read it every minute so a screen left open notices
// when the rules make a review due, the way the presence bar refreshes itself.
const AGENT_REFRESH_MS = 60_000;

const AssistantContext = createContext(null);

function addedLabel(count) {
  if (count === 0) return "Nothing to add.";
  if (count === 1) return "1 proposal added.";
  return `${count} proposals added.`;
}

export function AssistantProvider({ children }) {
  const { tick, refresh } = useHouse();
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [feedError, setFeedError] = useState(null);
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [notice, setNotice] = useState("");
  const [steps, setSteps] = useState([]);
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
    setFeedError(null);
    setNotice("");
    setReply("");
    setSteps(["received"]);
    try {
      const result = await feedAgent(value, {
        onStep(step) {
          if (mounted.current) setSteps((current) => noteStep(current, step));
        },
      });
      if (!mounted.current) return;
      setText("");
      setReply(result.reply || addedLabel(result.proposals?.length ?? 0));
      setSteps((current) => noteStep(current, "done"));
      await load();
    } catch (err) {
      if (!mounted.current) return;
      setSteps((current) => noteStep(current, "failed"));
      setFeedError(err?.message || "The assistant did not finish. Nothing was changed.");
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

  const enabled = Boolean(state?.enabled);
  const paused = Boolean(state?.paused);
  const proposals = state?.proposals ?? [];
  const replyLine = reply || (steps.length === 0 ? state?.last_reply?.text || "" : "");

  const value = {
    state,
    error,
    feedError,
    text,
    setText,
    replyLine,
    notice,
    setNotice,
    steps,
    sorting,
    reviewing,
    pendingId,
    enabled,
    paused,
    proposals,
    submit,
    decide,
  };

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant() {
  const value = useContext(AssistantContext);
  if (!value) throw new Error("Assistant is outside its provider.");
  return value;
}
