import type { CommuteAdvisory, CommuteLeg, CommutePlace, CommutePlan } from "../../api/commute";
import { cx, empty, errorText, heading, lede, meta, notice, rowTitle } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { formatHouseTime } from "../status/format";

export type CommuteOverview = {
  count: string;
  summary: string;
  urgent: string | null;
};

function attention(advisory: CommuteAdvisory): string | null {
  if (advisory.state === "error" || advisory.state === "stale" || advisory.state === "limited") {
    return advisory.detail;
  }
  if (advisory.state === "fresh" && !/no line disruptions/i.test(advisory.detail)) {
    return advisory.detail;
  }
  return null;
}

/** Compact row for the Home overview. The count is the outward minutes when known. */
export function commuteOverview(plan: CommutePlan | null, error: Error | null): CommuteOverview {
  if (error) {
    return { count: "—", summary: "The commute could not be read.", urgent: error.message };
  }
  if (!plan) {
    return { count: "…", summary: "Checking the commute…", urgent: null };
  }
  if (!plan.shift) {
    return { count: "—", summary: plan.summary, urgent: null };
  }
  const count = plan.outward?.minutes != null ? String(plan.outward.minutes) : "—";
  const out = plan.outward?.clock ? `Out ${plan.outward.clock}` : "Out";
  const back = plan.back?.clock ? `back ${plan.back.clock}` : "back after the finish";
  const when = plan.shift.when === "upcoming" ? "Next shift" : plan.shift.overnight ? "Overnight" : "Today";
  return { count, summary: `${when} · ${out} · ${back}`, urgent: attention(plan.advisory) };
}

function placeLine(place: CommutePlace, noun: string): string {
  const name = place.label || noun;
  if (place.state === "missing") return `${noun} is not set. Not verified with a provider.`;
  if (place.state === "unusable") return `${noun} is set but could not be used. Not verified with a provider.`;
  const extra = place.note ? ` ${place.note}` : "";
  return `${name} is configured. Not verified with a provider.${extra}`;
}

function buffers(plan: CommutePlan): string {
  const arrive =
    plan.arrival_buffer_minutes === 0
      ? "Arrive at the start."
      : `Arrive ${plan.arrival_buffer_minutes} min before the start.`;
  const back =
    plan.return_buffer_minutes === 0
      ? "The return departs at the finish."
      : `The return departs ${plan.return_buffer_minutes} min after the finish.`;
  return `${arrive} ${back}`;
}

/**
 * Outward and return for the open Home pane. The advisory is in-app.
 * A disabled check says it is not active. Times are Europe/London.
 */
export function CommuteDetail({ plan, error }: { plan: CommutePlan | null; error: Error | null }) {
  return (
    <section aria-labelledby="commute-plan-title" data-panel="commute" data-state={plan?.advisory.state ?? (error ? "error" : "loading")}>
      <h2 id="commute-plan-title" className={heading}>
        Commute
      </h2>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {!plan && !error && <LoadingSkeleton label="Checking the commute…" />}
      {plan && (
        <>
          <p className={lede}>{plan.summary}</p>
          <p className={plan.advisory.state === "inactive" ? empty : notice} data-advisory={plan.advisory.state}>
            {plan.advisory.detail}
          </p>
          {plan.shift && (
            <ul className="m-0 list-none p-0">
              {plan.outward && <LegRow leg={plan.outward} title="Out" />}
              {plan.back && <LegRow leg={plan.back} title="Back" />}
            </ul>
          )}
          <p className={cx(meta, "mt-4")} data-places>
            {placeLine(plan.home, "Home")} {placeLine(plan.destination, "Destination")}
          </p>
          {plan.shift && <p className={cx(meta, "mt-2")}>{buffers(plan)}</p>}
        </>
      )}
    </section>
  );
}

function LegRow({ leg, title }: { leg: CommuteLeg; title: string }) {
  const lines = leg.lines.length > 0 ? leg.lines.join(", ") : null;
  const clock =
    leg.clock != null
      ? `${leg.role === "outward" ? "Leave" : "Departs"} ${leg.clock}`
      : formatHouseTime(leg.target);
  const note = leg.state === "planned" ? leg.detail.split(". ").slice(1).join(". ") : leg.detail;
  return (
    <li className="border-t border-[var(--line)] py-2" data-leg={leg.role}>
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className={cx(rowTitle, "m-0 min-w-0")}>{title}</h3>
        <p className={cx(meta, "m-0 min-w-0 font-mono tabular-nums")}>{leg.meta}</p>
      </div>
      <p className={cx(empty, "mt-2")}>
        {clock}
        {leg.minutes != null ? ` · ${leg.minutes} min` : ""}
        {lines ? ` · ${lines}` : ""}
      </p>
      {note ? <p className={cx(meta, "mt-2")}>{note}</p> : null}
    </li>
  );
}
