import { useEffect, useState } from "react";
import { getStatus, type HouseStatus } from "../../api/system";
import { errorText } from "../../arrival/ui";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { formatBytes, formatHouseTime } from "./format";

/**
 * Status on the Settings card. Health, version, the last Mistral success,
 * the last activity poll, and the database size. No house text.
 */
export function StatusPanel() {
  const tick = useHouseTick();
  const [status, setStatus] = useState<HouseStatus | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStatus()
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
  }, [tick]);

  const health = status?.health === "ok" ? "Ok" : status?.health === "degraded" ? "Degraded" : "…";
  const rows: Array<[string, string, string]> = [
    ["Health", health, "health"],
    ["Version", status?.version ?? "…", "version"],
    ["Last Mistral success", status ? formatHouseTime(status.last_mistral_success) : "…", "mistral"],
    ["Last activity poll", status ? formatHouseTime(status.last_activity_poll) : "…", "poll"],
    ["Database", status ? formatBytes(status.database_bytes) : "…", "database"],
  ];

  return (
    <section className="mt-6" aria-labelledby="status-title" data-panel="status">
      <h3 id="status-title" className="serif m-0 text-[1.35rem] font-medium leading-tight tracking-[-0.02em] text-[var(--ink)]">
        Status
      </h3>
      <p className="mb-3 mt-2 text-[0.95rem] leading-normal text-[var(--muted)]">
        This process only. Nothing here is sent on.
      </p>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      <dl className="m-0 p-0">
        {rows.map(([label, value, key]) => (
          <div key={key} className="m-0 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-[var(--line)] py-2">
            <dt className="text-[0.95rem] font-normal text-[var(--muted)]">{label}</dt>
            <dd
              className={
                value === "Ok"
                  ? "m-0 text-[0.95rem] font-semibold text-success"
                  : value === "Degraded"
                    ? "m-0 text-[0.95rem] font-semibold text-[var(--danger)]"
                    : "m-0 text-[0.95rem] font-semibold text-[var(--ink)]"
              }
              data-status={key}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
