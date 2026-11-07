import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { applyProposal, dismissProposal, feedAgent, getAgent, runReview } from "../../api/agent";
import type { AgentDue, AgentState, Proposal } from "../../api/types";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { noteStep, type StepName } from "./steps";

const AGENT_REFRESH_MS = 60_000;

type AssistantValue = {
  state: AgentState | null;
  error: Error | null;
  feedError: string | null;
  text: string;
  setText: (value: string) => void;
  replyLine: string;
  notice: string;
  setNotice: (value: string) => void;
  steps: StepName[];
  sorting: boolean;
  reviewing: boolean;
  pendingId: string | null;
  enabled: boolean;
  reachable: boolean;
  paused: boolean;
  proposals: Proposal[];
  submit: (event: FormEvent) => Promise<void>;
  decide: (proposal: Proposal, action: "apply" | "dismiss", memoryIds?: string[]) => Promise<void>;
};

const AssistantContext = createContext<AssistantValue | null>(null);

function addedLabel(count: number) {
  if (count === 0) return "Nothing to add.";
  if (count === 1) return "1 proposal added.";
  return `${count} proposals added.`;
}

export function AssistantProvider({ children }: { children: ReactNode }) {
  const { tick, refresh } = useHouse();
  const [state, setState] = useState<AgentState | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [notice, setNotice] = useState("");
  const [steps, setSteps] = useState<StepName[]>([]);
  const [sorting, setSorting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const reviewed = useRef(new Set<string>());
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
    } catch (err: unknown) {
      if (mounted.current) setError(asError(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [tick, load]);

  useEffect(() => {
    const id = window.setInterval(() => void load(), AGENT_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    const due = state?.due;
    if (state?.local_reminders === "on") return;
    if (!due || !state.enabled || state.paused || sorting) return;
    if (reviewed.current.has(due.window_key)) return;
    reviewed.current.add(due.window_key);
    setReviewing(true);
    runReview(due as AgentDue)
      .then((result) => {
        const replyText = (result as { reply?: string }).reply;
        if (mounted.current && replyText) setReply(replyText);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted.current) {
          setReviewing(false);
          void load();
        }
      });
  }, [state, sorting, load]);

  async function submit(event: FormEvent) {
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
    } catch (err: unknown) {
      if (!mounted.current) return;
      setSteps((current) => noteStep(current, "failed"));
      setFeedError(asError(err).message || "The assistant did not finish. Nothing was changed.");
      await load();
    } finally {
      if (mounted.current) setSorting(false);
    }
  }

  async function decide(proposal: Proposal, action: "apply" | "dismiss", memoryIds?: string[]) {
    setPendingId(proposal.id);
    setError(null);
    try {
      if (action === "apply") {
        const result = await applyProposal(proposal.id, memoryIds);
        setNotice(`Applied: ${result.applied.summary}`);
        refresh();
      } else {
        await dismissProposal(proposal.id);
        setNotice(proposal.origin === "proactive" ? "Not now. That item rests for 72 hours." : "Dismissed. Nothing changed.");
        await load();
      }
    } catch (err: unknown) {
      setError(asError(err));
      await load();
    } finally {
      setPendingId(null);
    }
  }

  const enabled = Boolean(state?.enabled);
  const reachable = Boolean(state?.reachable);
  const paused = Boolean(state?.paused);
  const proposals = state?.proposals ?? [];
  const replyLine = reply || (steps.length === 0 ? state?.last_reply?.text || "" : "");

  const value: AssistantValue = {
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
    reachable,
    paused,
    proposals,
    submit,
    decide,
  };

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant(): AssistantValue {
  const value = useContext(AssistantContext);
  if (!value) throw new Error("Assistant is outside its provider.");
  return value;
}
