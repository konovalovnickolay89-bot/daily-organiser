import { useEffect, useState } from "react";
import { approveRequest, listApprovals, skipRequest } from "../../api/approvals";
import type { ApprovalItem } from "../../api/types";
import { cx, errorText, ghost, heading, lede, notice, primary } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { MODE_LABELS } from "../../lib/labels";
import { useAssistant } from "./AssistantContext";
import { orderedSteps, STEP_LABEL, type StepName } from "./steps";

function Ticker({
  steps,
  enabled,
  paused,
  loading,
  known,
}: {
  steps: StepName[];
  enabled: boolean;
  paused: boolean;
  loading: boolean;
  known: boolean;
}) {
  const line = "serif m-0 text-[1.28rem] font-medium leading-[1.28] tracking-[-0.02em] text-[var(--ink)]";
  if (loading) return <p className={cx(line, "text-[var(--muted)]")}>Checking the assistant…</p>;
  if (!known) return null;
  if (!enabled) return <p className={line}>The assistant is off.</p>;
  if (paused) {
    return (
      <div className="grid gap-2.5" role="status">
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
    <div className="grid gap-2.5" role="status" aria-live="polite">
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
              active && "before:mr-[0.55rem] before:inline-block before:h-[0.46rem] before:w-[0.46rem] before:-translate-y-[0.12rem] before:rounded-full before:bg-accent before:content-['']",
            )}
          >
            {STEP_LABEL[step]}
          </p>
        );
      })}
    </div>
  );
}

function DecisionButtons({ busy, onApply, onDismiss }: { busy: boolean; onApply: () => void; onDismiss: () => void }) {
  return (
    <div className="mt-3.5 flex flex-wrap items-center gap-x-2.5 gap-y-2">
      <button type="button" className={primary} disabled={busy} onClick={onApply}>
        Apply
      </button>
      <button type="button" className={cx(ghost, "font-medium text-[var(--muted)]")} disabled={busy} onClick={onDismiss}>
        Not now
      </button>
    </div>
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
  if (approvals === null && !approvalError) return null;
  if (proposals.length === 0 && waiting.length === 0) {
    if (hideEmpty) return null;
    return <p className="text-[0.9rem] text-[var(--muted)]">Nothing is waiting.</p>;
  }
  return (
    <>
      {approvalError && (
        <p className={errorText} role="alert">
          {approvalError.message}
        </p>
      )}
      <ul className="m-0 mt-1 grid list-none gap-3 p-0" data-surface="decisions">
        {waiting.map((item) => (
          <li key={`approval-${item.id}`} className="w-full min-w-0 rounded-house border border-[var(--line)] bg-card px-4 pb-3.5 pt-4" data-kind="approval">
            <p className="mb-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-ink">{MODE_LABELS[item.mode] ?? item.mode}</p>
            <h3 className="serif m-0 text-[1.2rem] font-medium leading-[1.25] tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]">{item.title}</h3>
            {item.detail && <p className="mt-2 text-[0.9rem] leading-snug text-[var(--muted)] [overflow-wrap:anywhere]">{item.detail}</p>}
            {item.mode === "execute" && <p className="mt-2 text-[0.9rem] text-[var(--muted)]">Applying records the decision only. Nothing is sent.</p>}
            <DecisionButtons busy={busyId === item.id} onApply={() => void decideApproval(item, "apply")} onDismiss={() => void decideApproval(item, "not-now")} />
          </li>
        ))}
        {proposals.map((proposal) => (
          <li key={`proposal-${proposal.id}`} className="w-full min-w-0 rounded-house border border-[var(--line)] bg-card px-4 pb-3.5 pt-4" data-origin={proposal.origin} data-kind="proposal">
            <p className="mb-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-ink">{proposal.label}</p>
            <h3 className="serif m-0 text-[1.2rem] font-medium leading-[1.25] tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]">{proposal.summary}</h3>
            <p className="mt-2 text-[0.9rem] leading-snug text-[var(--muted)] [overflow-wrap:anywhere]">{proposal.reason}</p>
            <DecisionButtons busy={pendingId === proposal.id} onApply={() => void decide(proposal, "apply")} onDismiss={() => void decide(proposal, "dismiss")} />
          </li>
        ))}
      </ul>
    </>
  );
}

/** Working strip, then the cards. The next Add replaces the strip. There is no thread. */
export function AssistantResult({ heading: showHeading = true }: { heading?: boolean }) {
  const { state, error, feedError, replyLine, notice: note, steps, reviewing, enabled, paused, sorting } = useAssistant();
  const loading = state === null && !error;

  return (
    <div>
      <Ticker steps={steps} enabled={enabled} paused={paused} loading={loading} known={state !== null} />
      {!paused && replyLine && (
        <p className={cx(notice, "serif mt-3.5 text-[1.05rem] whitespace-pre-line")} role="status">
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
      <div className={showHeading ? "mt-[22px] border-t border-[var(--line)] pt-5" : "mt-1"}>
        {showHeading && (
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="reasoning-proposals-title" className={heading}>
              Decisions
            </h2>
          </div>
        )}
        {showHeading && <p className={lede}>Apply or not now. Nothing is sent, bought, or booked.</p>}
        {loading && <LoadingSkeleton label="Looking for decisions…" />}
        {reviewing && <p className="text-[0.9rem] text-[var(--muted)]">Looking over the log…</p>}
        <DecisionList hideEmpty={sorting || reviewing || loading} />
      </div>
    </div>
  );
}
