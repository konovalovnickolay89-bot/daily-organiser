import { useEffect, useState, type FormEvent } from "react";
import { addXWatch, disconnectX, getXStatus, removeXWatch, startXConnect, type XStatus } from "../../api/x";
import { actions, cx, dialog, errorText, fieldInput, ghost, heading, kickerMuted, lede, primary, subheading } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { useHouseDialog } from "../../lib/dialog";

function DisconnectDialog({ busy, error, onDisconnect, onClose }: { busy: boolean; error: string | null; onDisconnect: () => void; onClose: () => void }) {
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  return (
    <dialog ref={dialogRef} className={dialog} aria-labelledby="x-disconnect-title">
      <h2 id="x-disconnect-title" className={heading}>
        Disconnect X?
      </h2>
      <p className={lede}>The refresh token is revoked. Bookmarks already kept stay in the log.</p>
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      <div className={actions}>
        <button type="button" className={primary} disabled={busy} onClick={onDisconnect}>
          Disconnect
        </button>
        <button type="button" className={ghost} disabled={busy} onClick={requestClose}>
          Cancel
        </button>
      </div>
    </dialog>
  );
}

/** Connect, disconnect, and the watch list. Tokens are not shown. */
export function XSettings() {
  const tick = useHouseTick();
  const [status, setStatus] = useState<XStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [kind, setKind] = useState<"account" | "keyword">("keyword");
  const [value, setValue] = useState("");
  const [flag, setFlag] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mark = params.get("x");
    if (mark) {
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
          setStatus(data);
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

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const { authorize_url: url } = await startXConnect();
      window.location.assign(url);
    } catch (err: unknown) {
      setError(asError(err).message);
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      setStatus(await disconnectX());
      setConfirming(false);
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    const next = value.trim();
    if (!next || busy) return;
    setBusy(true);
    setError(null);
    try {
      await addXWatch(kind, next);
      setStatus(await getXStatus());
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
      setStatus(await removeXWatch(id));
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8" aria-labelledby="x-settings-title" data-panel="x-settings">
      <h3 id="x-settings-title" className={subheading}>
        X
      </h3>
      {!status && !error && <LoadingSkeleton label="Checking X…" />}
      {status && !status.enabled && <p className={lede}>X is off.</p>}
      {status?.enabled && !status.configured && <p className={lede}>X is not configured.</p>}
      {status?.enabled && status.configured && !status.connected && (
        <div className="mt-2">
          <p className={lede}>Not connected.</p>
          <button type="button" className={primary} disabled={busy} onClick={() => void connect()}>
            Connect
          </button>
        </div>
      )}
      {status?.connected && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
          <p className="m-0 text-base font-semibold text-[var(--ink)]">
            Connected as <span className="font-mono tabular-nums">@{status.username}</span>
          </p>
          <button type="button" className={ghost} disabled={busy} onClick={() => setConfirming(true)}>
            Disconnect
          </button>
        </div>
      )}
      {flag === "failed" && <p className={lede}>X did not connect.</p>}
      {flag === "denied" && <p className={lede}>X connect was cancelled.</p>}
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      {status?.enabled && (
        <form className="mt-4" onSubmit={(event) => void add(event)}>
          <p className={cx(kickerMuted, "mb-2")}>Watch list</p>
          {status.watches.length > 0 && (
            <ul className="m-0 mb-2 list-none p-0">
              {status.watches.map((item) => (
                <li key={item.id} className="flex min-h-11 items-center justify-between gap-4">
                  <span className="font-mono tabular-nums">{item.kind === "account" ? `@${item.value}` : item.value}</span>
                  <button type="button" className={ghost} disabled={busy} onClick={() => void remove(item.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <label className="sr-only" htmlFor="x-watch-kind">
              Watch kind
            </label>
            <select
              id="x-watch-kind"
              className={cx(fieldInput, "w-auto")}
              value={kind}
              disabled={busy}
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
              className={cx(fieldInput, "min-w-0 flex-1")}
              value={value}
              maxLength={80}
              autoComplete="off"
              placeholder={kind === "account" ? "Handle" : "Keyword"}
              disabled={busy}
              onChange={(event) => setValue(event.target.value)}
            />
            <button type="submit" className={cx(ghost, "shrink-0")} disabled={busy || value.trim() === ""}>
              Add
            </button>
          </div>
        </form>
      )}
      {confirming && (
        <DisconnectDialog
          busy={busy}
          error={error}
          onDisconnect={() => void disconnect()}
          onClose={() => setConfirming(false)}
        />
      )}
    </section>
  );
}
