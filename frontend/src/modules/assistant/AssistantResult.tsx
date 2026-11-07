import { useEffect, useState } from "react";
import { approveRequest, listApprovals, skipRequest } from "../../api/approvals";
import type { ApprovalItem, Proposal } from "../../api/types";
import { SectionHeader } from "../../arrival/SectionHeader";
import { actions, cx, empty, errorText, ghost, inset, kickerAccent, meta, notice, primary, subheading } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { MODE_LABELS } from "../../lib/labels";
import { usedMemoriesLabel } from "../memory/copy";
import { ReminderPreview } from "../reminders/ReminderPreview";
import { XCards } from "../x/XCards";
import { useAssistant } from "./AssistantContext";
import { orderedSteps, STEP_LABEL, type StepName } from "./steps";

function Ticker({
  steps,
  enabled,
  reachable,
  paused,
  loading,
  known,
}: {
  steps: StepName[];
  enabled: boolean;
  reachable: boolean;
  paused: boolean;
  loading: boolean;
  known: boolean;
}) {
  const line = "ticker-line serif m-0 text-xl font-medium leading-tight tracking-[-0.02em] text-[var(--ink)]";
  if (loading) return <p className={cx(line, "text-[var(--muted)]")}>Checking the assistant…</p>;
  if (!known) return null;
  if (!enabled) return <p className={line}>The assistant is off.</p>;
  if (!reachable) return <p className={line}>The assistant is down.</p>;
  if (paused) {
    return (
      <div className="grid gap-2" role="status">
        <p className={line}>Paused.</p>
        <p className={cx(line, "text-[var(--muted)]")}>Nothing goes to the assistant.</p>
      </div>
    );
  }
  if (steps.length === 0) {
    return (
      <p className={line} role="status">
        Quiet.
      </p>
    );
  }

  const ordered = orderedSteps(steps);
  const current = steps[steps.length - 1];
  return (
    <div className="grid gap-2" role="status" aria-live="polite">
      {ordered.map((step) => {
        const active = step === current && step !== "done" && step !== "failed";
        const finished = current === "done";
        const settled = !finished && !active && step !== "failed" && step !== current;
        return (
          <p
            key={step}
            className={cx(
              line,
              step === "failed" && "text-[var(--danger)]",
              settled && "text-[var(--muted)]",
              active && "before:mr-2 before:inline-block before:h-2 before:w-2 before:rounded-full before:bg-accent before:content-['']",
            )}
          >
            {STEP_LABEL[step]}
          </p>
        );
      })}
    </div>
  );
}

function DecisionButtons({
  busy,
  applyDisabled = false,
  applyLabel = "Apply",
  dismissLabel = "Not now",
  onApply,
  onDismiss,
}: {
  busy: boolean;
  applyDisabled?: boolean;
  applyLabel?: string;
  dismissLabel?: string;
  onApply: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className={actions}>
      <button type="button" className={primary} disabled={busy || applyDisabled} onClick={onApply}>
        {applyLabel}
      </button>
      <button type="button" className={cx(ghost, "font-medium text-[var(--muted)]")} disabled={busy} onClick={onDismiss}>
        {dismissLabel}
      </button>
    </div>
  );
}

function ProposalCard({
  proposal,
  busy,
  onApply,
  onDismiss,
}: {
  proposal: Proposal;
  busy: boolean;
  onApply: (memoryIds?: string[]) => void;
  onDismiss: () => void;
}) {
  const matches = proposal.action === "forget" ? proposal.matches ?? [] : [];
  const [chosen, setChosen] = useState<string[]>(() => matches.map((item) => item.id));
  const used = usedMemoriesLabel(proposal.memories_used);

  function toggle(id: string) {
    setChosen((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <li className={cx(inset, "proposal-card")} data-origin={proposal.origin} data-kind="proposal">
      <p className={cx(kickerAccent, "mb-2")}>{proposal.label}</p>
      <h3 className={subheading}>{proposal.summary}</h3>
      <p className={cx(meta, "mt-2 [overflow-wrap:anywhere]")}>{proposal.reason}</p>
      {used && <p className="mt-2 text-sm font-semibold leading-snug text-accent-ink">{used}</p>}
      {matches.length > 0 && (
        <ul className="m-0 mt-4 grid list-none gap-2 p-0">
          {matches.map((match) => (
            <li key={match.id}>
              <label className="flex min-h-11 items-center gap-4 text-base text-[var(--ink)]">
                <input
                  className="h-6 w-6 accent-accent"
                  type="checkbox"
                  checked={chosen.includes(match.id)}
                  onChange={() => toggle(match.id)}
                />
                <span className="[overflow-wrap:anywhere]">{match.text}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {proposal.date_note && <p className="mt-2 text-sm font-semibold leading-snug text-accent-ink">{proposal.date_note}</p>}
      <DecisionButtons
        busy={busy}
        applyDisabled={matches.length > 0 && chosen.length === 0}
        onApply={() => onApply(matches.length > 0 ? chosen : undefined)}
        onDismiss={onDismiss}
      />
    </li>
  );
}

function DecisionList({ hideEmpty }: { hideEmpty: boolean }) {
  const { tick, refresh } = useHouse();
  const { proposals, pendingId, decide, setNotice } = useAssistant();
  const [approvals, setApprovals] = useState<ApprovalItem[] | null>(null);
  const [approvalError, setApprovalError] = useState<Error | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listApprovals("pending")
      .then((data) => {
        if (!cancelled) {
          setApprovals(data.items);
          setApprovalError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setApprovalError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  async function decideApproval(item: ApprovalItem, action: "apply" | "not-now") {
    setBusyId(item.id);
    setApprovalError(null);
    try {
      const result = action === "apply" ? await approveRequest(item.id) : await skipRequest(item.id);
      setNotice(result.effect?.summary || "Decision recorded. Nothing left the house.");
      refresh();
    } catch (err: unknown) {
      setApprovalError(asError(err));
    } finally {
      setBusyId(null);
    }
  }

  const waiting = approvals ?? [];
  return (
    <XCards
      render={(x) => {
        if (approvals === null && !approvalError) return null;
        const nothing = proposals.length === 0 && waiting.length === 0 && x.empty && !x.loading;
        if (nothing) {
          if (hideEmpty) return null;
          return <p className={empty}>Nothing is waiting.</p>;
        }
        return (
          <>
            {approvalError && (
              <p className={errorText} role="alert">
                {approvalError.message}
              </p>
            )}
            {x.notice}
            {x.error}
            <ul className="m-0 mt-2 grid list-none gap-4 p-0" data-surface="decisions">
              {waiting.map((item) => (
                <li key={`approval-${item.id}`} className={cx(inset, "proposal-card")} data-kind="approval">
                  <p className={cx(kickerAccent, "mb-2")}>{MODE_LABELS[item.mode] ?? item.mode}</p>
                  <h3 className={subheading}>{item.title}</h3>
                  {item.detail && <p className={cx(meta, "mt-2 [overflow-wrap:anywhere]")}>{item.detail}</p>}
                  {item.mode === "execute" && (
                    <p className={cx(meta, "mt-2")}>Approve records the decision only. Nothing is sent.</p>
                  )}
                  <DecisionButtons
                    busy={busyId === item.id}
                    applyLabel="Approve"
                    dismissLabel="Not now"
                    onApply={() => void decideApproval(item, "apply")}
                    onDismiss={() => void decideApproval(item, "not-now")}
                  />
                </li>
              ))}
              {proposals.map((proposal) => (
                <ProposalCard
                  key={`proposal-${proposal.id}`}
                  proposal={proposal}
                  busy={pendingId === proposal.id}
                  onApply={(memoryIds) => void decide(proposal, "apply", memoryIds)}
                  onDismiss={() => void decide(proposal, "dismiss")}
                />
              ))}
              {x.rows}
            </ul>
            {x.dialog}
          </>
        );
      }}
    />
  );
}

/** Working strip, then the cards. The next Add replaces the strip. There is no thread. */
export function AssistantResult({ heading: showHeading = true }: { heading?: boolean }) {
  const { state, error, feedError, replyLine, notice: note, steps, reviewing, enabled, reachable, paused, sorting } = useAssistant();
  const loading = state === null && !error;

  return (
    <div>
      <Ticker steps={steps} enabled={enabled} reachable={reachable} paused={paused} loading={loading} known={state !== null} />
      {!paused && replyLine && (
        <p className={cx(notice, "serif mt-4 text-base whitespace-pre-line")} role="status">
          {replyLine}
        </p>
      )}
      {!paused && note && (
        <p className={notice} role="status">
          {note}
        </p>
      )}
      {!paused && feedError && (
        <p className={errorText} role="alert">
          {feedError}
        </p>
      )}
      {!paused && error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {showHeading ? (
        <SectionHeader
          id="reasoning-proposals-title"
          title="Decisions"
          divided
          note="One queue. Approve, Apply, Keep, or Post names the action. Nothing is sent unless you confirm a post."
        />
      ) : (
        <div className="mt-2" />
      )}
      <ReminderPreview />
      <div>
        {loading && <LoadingSkeleton label="Looking for decisions…" />}
        {reviewing && <p className={empty}>Looking over the log…</p>}
        <DecisionList hideEmpty={sorting || reviewing || loading} />
      </div>
    </div>
  );
}
