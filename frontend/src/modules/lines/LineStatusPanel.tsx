import type { LineStatus, TransitLine } from "../../api/lines";
import { cx, empty, errorText, heading, lede, meta, notice, rowTitle } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { formatHouseTime } from "../status/format";

export type LineOverview = {
  count: string;
  summary: string;
  urgent: string | null;
};

const GOOD = "good service";

function disrupted(lines: TransitLine[]): TransitLine[] {
  return lines.filter((line) => line.severity.trim().toLowerCase() !== GOOD);
}

/**
 * Compact row for the Home overview. The count is how many lines are disrupted.
 * A stale or failed read stays on the row, so it is visible with another section open.
 */
export function lineOverview(status: LineStatus | null, error: Error | null): LineOverview {
  if (error) {
    return { count: "—", summary: "Line status could not be read.", urgent: error.message };
  }
  if (!status) {
    return { count: "…", summary: "Checking line status…", urgent: null };
  }
  if (status.state === "missing") {
    return { count: "—", summary: status.detail ?? "TfL is not configured.", urgent: null };
  }
  if (status.state === "error") {
    const detail = status.detail ?? "Line status is unavailable.";
    return { count: "—", summary: "Line status is unavailable.", urgent: detail };
  }
  const problems = disrupted(status.lines);
  const count = String(problems.length);
  const summary =
    problems.length === 0
      ? status.detail || "Good service."
      : problems.length === 1
        ? "1 line disrupted."
        : `${problems.length} lines disrupted.`;
  const first = problems[0];
  const attention = first ? `${first.name}: ${first.severity}` : null;
  if (status.state === "stale") {
    return {
      count,
      summary,
      urgent: attention ? `A newer read failed. ${attention}` : "A newer read failed.",
    };
  }
  return { count, summary, urgent: attention };
}

/**
 * Per-line detail for the Home pane. Timestamps are the fetch and the source
 * time. A stale read says the newer read failed. It does not say the board is live.
 */
export function LineStatusDetail({ status, error }: { status: LineStatus | null; error: Error | null }) {
  return (
    <section aria-labelledby="line-status-title" data-panel="lines" data-state={status?.state ?? (error ? "error" : "loading")}>
      <h2 id="line-status-title" className={heading}>
        Line status
      </h2>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {!status && !error && <LoadingSkeleton label="Checking line status…" />}
      {status && (
        <>
          <p className={status.state === "stale" ? notice : lede} data-readout>
            {readout(status)}
          </p>
          {status.lines.length > 0 && (
            <ul className="m-0 list-none p-0">
              {status.lines.map((line) => (
                <LineRow key={line.id} line={line} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function readout(status: LineStatus): string {
  if (status.state === "missing" || status.state === "error") {
    return status.detail ?? "Line status is unavailable.";
  }
  const read = status.fetched_at ? `Read at ${formatHouseTime(status.fetched_at)}.` : "";
  const source = status.source_at ? `Source time ${formatHouseTime(status.source_at)}.` : "";
  const times = [read, source].filter(Boolean).join(" ");
  if (status.state === "stale") {
    return [status.detail ?? "Showing the last line status. A newer read failed.", times].filter(Boolean).join(" ");
  }
  if (status.detail) return [status.detail, times].filter(Boolean).join(" ");
  return times || "Line status.";
}

function tone(severity: string): string {
  const value = severity.toLowerCase();
  if (value === GOOD) return "text-success";
  if (value.includes("delay") || value.includes("closed") || value.includes("suspend")) return "text-[var(--danger)]";
  return "text-[var(--ink)]";
}

function LineRow({ line }: { line: TransitLine }) {
  return (
    <li className="border-t border-[var(--line)] py-2" data-line={line.id}>
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className={cx(rowTitle, "m-0 min-w-0")}>{line.name}</h3>
        <p className={cx(meta, "m-0 min-w-0")}>
          <span>{line.mode}</span>
          <span className="px-2" aria-hidden="true">
            ·
          </span>
          <span className={tone(line.severity)} data-severity>
            {line.severity}
          </span>
        </p>
      </div>
      {line.reason ? (
        <p className={cx(empty, "mt-2 min-w-0 [overflow-wrap:anywhere]")} data-reason>
          {line.reason}
        </p>
      ) : null}
    </li>
  );
}
