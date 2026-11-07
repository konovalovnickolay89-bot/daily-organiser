import { useEffect, useState } from "react";
import { getStatus, type HouseStatus } from "../../api/system";
import { cx, errorText, lede, subheading } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { formatBytes, formatHouseTime, formatXLine } from "./format";

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
  const serviceLabel: Record<string, string> = {
    mistral: "Mistral",
    voxtral: "Voxtral",
    google: "Google",
    tfl: "TfL",
    x: "X",
    hearthis: "hearthis",
  };
  const serviceValue = (state: string) => {
    if (state === "ok" || state === "ready") return "Ok";
    if (state === "attention") return "Attention";
    if (state === "off") return "Off";
    if (state === "not configured") return "Not configured";
    if (state === "unavailable") return "Unavailable";
    return "Not yet";
  };
  const rows: Array<[string, string, string]> = [
    ["Health", health, "health"],
    ["Version", status?.version ?? "…", "version"],
    ["Last Mistral success", status ? formatHouseTime(status.last_mistral_success) : "…", "mistral"],
    ["Last activity poll", status ? formatHouseTime(status.last_activity_poll) : "…", "poll"],
    ["Database", status ? formatBytes(status.database_bytes) : "…", "database"],
    ["X credits / rate", status ? formatXLine(status.x) : "…", "x"],
    ...(status?.services ?? []).map(
      (service): [string, string, string] => [
        serviceLabel[service.name] ?? service.name,
        serviceValue(service.state),
        `service-${service.name}`,
      ],
    ),
  ];

  return (
    <section className="mt-8" aria-labelledby="status-title" data-panel="status">
      <h3 id="status-title" className={subheading}>
        Status
      </h3>
      <p className={lede}>This process only. Nothing here is sent on.</p>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {!status && !error && <LoadingSkeleton label="Checking status…" />}
      {status && (
      <dl className="m-0 p-0">
        {rows.map(([label, value, key]) => (
          <div key={key} className="m-0 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-t border-[var(--line)] py-2">
            <dt className="text-base font-normal text-[var(--muted)]">{label}</dt>
            <dd
              className={cx(
                "m-0 text-base font-semibold",
                value === "Ok" ? "text-success" : value === "Degraded" || value === "Attention" || value === "Unavailable" ? "text-[var(--danger)]" : "text-[var(--ink)]",
                key !== "health" && "font-mono tabular-nums",
              )}
              data-status={key}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>
      )}
    </section>
  );
}
