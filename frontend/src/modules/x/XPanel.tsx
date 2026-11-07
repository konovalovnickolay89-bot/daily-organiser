import { useEffect, useState, type FormEvent } from "react";
import {
  addXWatch,
  disconnectX,
  getXStatus,
  pauseXPoll,
  removeXWatch,
  resumeXPoll,
  startXConnect,
  type XErrorClass,
  type XStatus,
} from "../../api/x";
import { SectionHeader } from "../../arrival/SectionHeader";
import {
  actions,
  cx,
  dialog,
  errorText,
  fieldInput,
  ghost,
  heading,
  kickerMuted,
  lede,
  primary,
} from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse, useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { useHouseDialog } from "../../lib/dialog";
import { formatHouseTime } from "../status/format";
import { XCards } from "./XCards";
import { watchValueError } from "./watch";

const ERROR_COPY: Record<XErrorClass, string> = {
  auth: "X refused the saved connection. Reconnect when you mean to.",
  credits: "X reported no credits remaining. Reading waits.",
  rate: "X reported a rate limit. Reading waits.",
  unreachable: "X could not be reached.",
  http: "X returned an error. Reading waits.",
};

const KNOWN_ERRORS = new Set<string>(Object.keys(ERROR_COPY));

function knownError(value: string | null | undefined): XErrorClass | null {
  if (value && KNOWN_ERRORS.has(value)) return value as XErrorClass;
  return null;
}

function filled(data: XStatus): XStatus {
  return {
    ...data,
    watches: data.watches ?? [],
    poll_paused: Boolean(data.poll_paused),
    poll_interval_minutes: data.poll_interval_minutes ?? null,
    last_poll_at: data.last_poll_at ?? null,
    last_error_class: knownError(data.last_error_class),
    backing_off: Boolean(data.backing_off),
    backoff_until: data.backoff_until ?? null,
    credits_remaining: data.credits_remaining ?? null,
    rate_remaining: data.rate_remaining ?? null,
    rate_reset_at: data.rate_reset_at ?? null,
    watch_limit: data.watch_limit ?? 20,
  };
}

function phase(status: XStatus | null, failed: boolean): string {
  if (!status) return failed ? "error" : "loading";
  if (!status.enabled) return "off";
  if (!status.configured) return "unconfigured";
  if (!status.connected) return "disconnected";
  if (status.last_error_class || status.backing_off) return "attention";
  return "connected";
}

function headerValue(value: number | null | undefined): string {
  if (value == null) return "Not reported";
  return String(value);
}

function ConfirmDialog({
  titleId,
  title,
  body,
  confirmLabel,
  busy,
  error,
  onConfirm,
  onClose,
}: {
  titleId: string;
  title: string;
  body: string;
  confirmLabel: string;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  return (
    <dialog ref={dialogRef} className={dialog} aria-labelledby={titleId}>
      <h2 id={titleId} className={heading}>
        {title}
      </h2>
      <p className={lede}>{body}</p>
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      <div className={actions}>
        <button type="button" className={primary} disabled={busy} onClick={onConfirm}>
          {confirmLabel}
        </button>
        <button type="button" className={ghost} disabled={busy} onClick={requestClose}>
          Cancel
        </button>
      </div>
    </dialog>
  );
}

/**
 * Connection, watches, and reading for this house.
 * Tokens stay on the server. A post still needs Post, then confirm, on a draft card.
 */
export function XPanel() {
  const tick = useHouseTick();
  const housePaused = Boolean(useHouse().system?.paused);
  const [status, setStatus] = useState<XStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<null | "connect" | "disconnect" | "reconnect">(null);
  const [kind, setKind] = useState<"account" | "keyword">("keyword");
  const [value, setValue] = useState("");
  const [flag, setFlag] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mark = params.get("x");
    if (mark === "failed" || mark === "denied") {
      setFlag(mark);
      params.delete("x");
      const next = params.toString();
      window.history.replaceState(null, "", next ? `?${next}` : window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getXStatus()
      .then((data) => {
        if (!cancelled) {
          setStatus(filled(data));
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err).message);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const typed = value.trim();
  const fieldError = typed === "" ? null : watchValueError(kind, value);
  const limit = status?.watch_limit ?? 20;
  const full = Boolean(status && status.watches.length >= limit);
  const enabled = Boolean(status?.enabled);
  const configured = Boolean(status?.configured);
  const connected = Boolean(status?.connected);

  async function openAllowPage() {
    const { authorize_url: url } = await startXConnect();
    try {
      window.location.assign(url);
    } catch {
      setError("The allow page did not open.");
      setBusy(false);
    }
  }

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      await openAllowPage();
    } catch (err: unknown) {
      setError(asError(err).message);
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      setStatus(filled(await disconnectX()));
      setPending(null);
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function reconnect() {
    setBusy(true);
    setError(null);
    try {
      setStatus(filled(await disconnectX()));
      await openAllowPage();
    } catch (err: unknown) {
      setError(asError(err).message);
      setBusy(false);
    }
  }

  async function toggleReading() {
    if (!status?.enabled || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = status.poll_paused ? await resumeXPoll() : await pauseXPoll();
      setStatus(filled(next));
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const message = watchValueError(kind, value);
    if (!status?.enabled || message || full || busy) return;
    setBusy(true);
    setError(null);
    try {
      await addXWatch(kind, value.trim());
      setStatus(filled(await getXStatus()));
      setValue("");
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    setError(null);
    try {
      setStatus(filled(await removeXWatch(id)));
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  const errorCopy = status?.last_error_class ? ERROR_COPY[status.last_error_class] : null;
  const waiting = status?.backing_off
    ? `Reading waits until ${formatHouseTime(status.backoff_until ?? null)}.`
    : null;

  return (
    <section aria-labelledby="x-panel-title" data-module="x-panel" data-x-state={phase(status, Boolean(error))}>
      <SectionHeader
        id="x-panel-title"
        title="X"
        note="This house app. Connect, watch, and read. A post still needs Post, then confirm."
      />
      {!status && !error && <LoadingSkeleton label="Checking X…" />}
      {status && !status.enabled && (
        <p className={lede}>X is off. The house file has to turn it on. This screen cannot.</p>
      )}
      {status?.enabled && !status.configured && (
        <p className={lede}>X is not configured. Connect stays closed until the house file has the app. This screen does not take a key.</p>
      )}
      {status?.enabled && status.configured && !status.connected && (
        <p className={lede}>Not connected. Connect opens X so you can allow this house app. Nothing is posted from here.</p>
      )}
      {connected && (
        <p className="m-0 text-base font-semibold text-[var(--ink)]">
          Connected as <span className="font-mono tabular-nums">@{status?.username}</span>
        </p>
      )}
      {flag === "failed" && (
        <p className={lede}>X did not connect. If the allow page failed before coming back, this house never got a callback.</p>
      )}
      {flag === "denied" && <p className={lede}>X connect was cancelled.</p>}
      {error && !pending && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      {status && (
        <div className={actions}>
          {!connected && (
            <button
              type="button"
              className={primary}
              disabled={busy || !enabled || !configured}
              onClick={() => {
                setError(null);
                setPending("connect");
              }}
            >
              Connect
            </button>
          )}
          {connected && (
            <button
              type="button"
              className={ghost}
              disabled={busy}
              onClick={() => {
                setError(null);
                setPending("reconnect");
              }}
            >
              Reconnect
            </button>
          )}
          {connected && (
            <button
              type="button"
              className={ghost}
              disabled={busy}
              onClick={() => {
                setError(null);
                setPending("disconnect");
              }}
            >
              Disconnect
            </button>
          )}
        </div>
      )}

      {status && (
        <form className="mt-8" onSubmit={(event) => void add(event)}>
          <p className={cx(kickerMuted, "mb-2")}>Watch list</p>
          {full && <p className={lede}>The watch list is full ({limit}). Remove one before adding another.</p>}
          {status.watches.length > 0 && (
            <ul className="m-0 mb-2 list-none p-0">
              {status.watches.map((item) => {
                const label = item.kind === "account" ? `@${item.value.replace(/^@/, "")}` : item.value;
                return (
                  <li key={item.id} className="flex min-h-11 items-center justify-between gap-4">
                    <span className="min-w-0 font-mono tabular-nums [overflow-wrap:anywhere]">{label}</span>
                    <button
                      type="button"
                      className={cx(ghost, "shrink-0")}
                      disabled={busy || !enabled}
                      aria-label={`Remove ${label}`}
                      onClick={() => void remove(item.id)}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="grid gap-2">
            <label className="sr-only" htmlFor="x-watch-kind">
              Watch kind
            </label>
            <select
              id="x-watch-kind"
              className={fieldInput}
              value={kind}
              disabled={busy || !enabled}
              onChange={(event) => setKind(event.target.value as "account" | "keyword")}
            >
              <option value="keyword">Keyword</option>
              <option value="account">Account</option>
            </select>
            <label className="sr-only" htmlFor="x-watch-value">
              Watch
            </label>
            <input
              id="x-watch-value"
              className={fieldInput}
              value={value}
              maxLength={80}
              autoComplete="off"
              placeholder={kind === "account" ? "Handle" : "Keyword"}
              disabled={busy || !enabled}
              aria-invalid={fieldError ? true : undefined}
              aria-describedby={fieldError ? "x-watch-error" : undefined}
              onChange={(event) => setValue(event.target.value)}
            />
            <button type="submit" className={cx(ghost, "justify-self-start")} disabled={busy || !enabled || typed === "" || Boolean(fieldError) || full}>
              Add
            </button>
          </div>
          {fieldError && (
            <p id="x-watch-error" className={cx(errorText, "mt-2")} role="alert">
              {fieldError}
            </p>
          )}
        </form>
      )}

      {status && (
        <div className="mt-8">
          <p className={cx(kickerMuted, "mb-2")}>Reading</p>
          <p className={lede}>
            {!enabled && "Reading stays off with X."}
            {enabled && status.poll_paused && "Reading is paused. Bookmarks and watches are not requested."}
            {enabled && !status.poll_paused && "Reading is allowed on the next check."}{" "}
            {enabled && status.poll_interval_minutes
              ? `The house file asks for a read about every ${status.poll_interval_minutes} minutes. This screen does not change that.`
              : ""}
          </p>
          {housePaused && <p className={lede}>The house is paused, so X is not read.</p>}
          <button
            type="button"
            className={ghost}
            disabled={busy || !enabled}
            aria-pressed={Boolean(status.poll_paused)}
            onClick={() => void toggleReading()}
          >
            {status.poll_paused ? "Resume reading" : "Pause reading"}
          </button>
          {enabled && (
            <>
              {errorCopy && <p className={lede}>{errorCopy}</p>}
              {waiting && <p className={lede}>{waiting}</p>}
              <dl className="m-0 mt-4 p-0">
                <ReadingRow label="Last read" value={formatHouseTime(status.last_poll_at ?? null)} />
                <ReadingRow label="Credits remaining" value={headerValue(status.credits_remaining)} />
                <ReadingRow label="Rate remaining" value={headerValue(status.rate_remaining)} />
                <ReadingRow label="Rate reset" value={status.rate_reset_at ? formatHouseTime(status.rate_reset_at) : "Not reported"} />
              </dl>
              <p className="mb-0 mt-2 text-base leading-normal text-[var(--muted)]">
                Last headers from X. This house does not set a spend cap. A blank header is shown as not reported.
              </p>
            </>
          )}
        </div>
      )}

      <XCards />

      {pending === "connect" && (
        <ConfirmDialog
          titleId="x-connect-title"
          title="Open X to connect?"
          body="You allow this house app on X. Nothing is posted. This page does not see the code."
          confirmLabel="Connect"
          busy={busy}
          error={error}
          onConfirm={() => void connect()}
          onClose={() => {
            if (!busy) setPending(null);
          }}
        />
      )}
      {pending === "disconnect" && (
        <ConfirmDialog
          titleId="x-disconnect-title"
          title="Disconnect X?"
          body="The refresh token is revoked. Bookmarks already kept stay in the log. Nothing is posted."
          confirmLabel="Disconnect"
          busy={busy}
          error={error}
          onConfirm={() => void disconnect()}
          onClose={() => {
            if (!busy) setPending(null);
          }}
        />
      )}
      {pending === "reconnect" && (
        <ConfirmDialog
          titleId="x-reconnect-title"
          title="Reconnect X?"
          body="The stored refresh token is revoked, then X opens so you can allow this house app again. Nothing is posted."
          confirmLabel="Reconnect"
          busy={busy}
          error={error}
          onConfirm={() => void reconnect()}
          onClose={() => {
            if (!busy) setPending(null);
          }}
        />
      )}
    </section>
  );
}

function ReadingRow({ label, value, plain = false }: { label: string; value: string; plain?: boolean }) {
  return (
    <div className="m-0 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-t border-[var(--line)] py-2">
      <dt className="min-w-0 text-base font-normal text-[var(--muted)]">{label}</dt>
      <dd className={cx("m-0 min-w-0 text-right text-base font-semibold text-[var(--ink)]", !plain && "font-mono tabular-nums")}>{value}</dd>
    </div>
  );
}
