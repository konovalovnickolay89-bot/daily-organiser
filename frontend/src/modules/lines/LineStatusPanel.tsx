import { useEffect, useState } from "react";
import { getLineStatus, type LineStatus, type TransitLine } from "../../api/lines";
import { useView } from "../../arrival/view";
import { cx, empty, errorText, lede, meta, notice, rowTitle, subheading } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { formatHouseTime } from "../status/format";

/**
 * Line status on the Settings card. The TfL row above says whether the key
 * is set. This says what the last read actually returned. It does not say
 * the board is live, and it does not fetch until Settings is open.
 */
export function LineStatusPanel() {
  const view = useView();
  const tick = useHouseTick();
  const [status, setStatus] = useState<LineStatus | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (view !== "settings") return undefined;
    let cancelled = false;
    getLineStatus()
      .then((data) => {
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [view, tick]);

  if (view !== "settings") return null;

  return (
    <section className="mt-8" aria-labelledby="line-status-title" data-panel="lines" data-state={status?.state ?? "loading"}>
      <h3 id="line-status-title" className={subheading}>
        Line status
      </h3>
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
  if (value === "good service") return "text-success";
  if (value.includes("delay") || value.includes("closed") || value.includes("suspend")) return "text-[var(--danger)]";
  return "text-[var(--ink)]";
}

function LineRow({ line }: { line: TransitLine }) {
  return (
    <li className="border-t border-[var(--line)] py-2" data-line={line.id}>
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h4 className={cx(rowTitle, "m-0 min-w-0")}>{line.name}</h4>
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
