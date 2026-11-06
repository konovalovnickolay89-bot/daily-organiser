import { useEffect, useState, type FormEvent } from "react";
import {
  getFeatureSettings,
  patchFeatureSettings,
  type FeatureSettings as FeatureSettingsBody,
} from "../../api/system";
import { cx, errorText, fieldHint, fieldInput, fieldLabel, fieldStack, ghost, kickerMuted, lede, meta, subheading } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";

function SwitchRow({
  label,
  checked,
  disabled,
  busy,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  busy: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="inline-flex min-h-11 cursor-pointer items-center gap-4">
      <input
        className="h-6 w-6 accent-accent"
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled || busy}
        aria-label={label}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="m-0 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-t border-[var(--line)] py-2">
      <dt className="text-base font-normal text-[var(--muted)]">{label}</dt>
      <dd className="m-0 text-right font-mono text-base font-medium tabular-nums text-[var(--ink)]">{value || "Not set"}</dd>
    </div>
  );
}

function NumberField({
  id,
  label,
  hint,
  min,
  max,
  value,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  min: number;
  max: number;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className={fieldStack} htmlFor={id}>
      <span className={fieldLabel}>{label}</span>
      <input
        id={id}
        className={cx(fieldInput, "font-mono tabular-nums")}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange(event.target.value)}
      />
      <span className={fieldHint}>{hint}</span>
    </label>
  );
}

/**
 * Persisted house choices. The assistant switch, theme, memory, and X connect
 * stay where they were. Nothing here shows a secret.
 */
export function FeatureSettings() {
  const { refresh } = useHouse();
  const [settings, setSettings] = useState<FeatureSettingsBody | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [sync, setSync] = useState("");
  const [daily, setDaily] = useState("");
  const [fromMax, setFromMax] = useState("");
  const [expiry, setExpiry] = useState("");
  const [tokens, setTokens] = useState("");
  const [memory, setMemory] = useState("");
  const [smartDays, setSmartDays] = useState("");
  const [catchDays, setCatchDays] = useState("");

  function apply(next: FeatureSettingsBody) {
    setSettings(next);
    setSync(String(next.x.sync_minutes));
    setDaily(String(next.x.daily_cap));
    setFromMax(String(next.x.from_max));
    setExpiry(String(next.x.draft_expiry_days));
    setTokens(String(next.agent_context.token_budget));
    setMemory(String(next.agent_context.memory_limit));
    setSmartDays(String(next.agent_context.smart_add_days));
    setCatchDays(String(next.agent_context.catch_up_days));
  }

  useEffect(() => {
    let cancelled = false;
    getFeatureSettings()
      .then((data) => {
        if (!cancelled) {
          apply(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(body: Record<string, boolean | number>, playlist = false) {
    setBusy(true);
    setError(null);
    try {
      const next = await patchFeatureSettings(body);
      apply(next);
      if (playlist) refresh();
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusy(false);
    }
  }

  function saveNumbers(event: FormEvent, body: Record<string, number>) {
    event.preventDefault();
    if (busy) return;
    void save(body);
  }

  return (
    <div data-panel="feature-settings">
      <section className="mt-8" aria-labelledby="playlist-title" data-panel="playlist">
        <h3 id="playlist-title" className={subheading}>
          Playlist
        </h3>
        <p className={lede}>The hearthis line. It links out. It does not play.</p>
        {!settings && !error && <LoadingSkeleton label="Loading playlist…" />}
        {settings && (
          <>
            <dl className="m-0 p-0">
              <Fact label="Source" value={settings.playlist.source} />
              <Fact label="Profile" value={settings.playlist.profile} />
            </dl>
            <div className="mt-2">
              <SwitchRow
                label="Playlist"
                checked={settings.playlist.enabled}
                disabled={!settings.playlist.available}
                busy={busy}
                onChange={(value) => void save({ playlist_enabled: value }, true)}
              />
            </div>
            {settings.playlist.detail && <p className={cx(meta, "mt-2")}>{settings.playlist.detail}</p>}
          </>
        )}
      </section>

      <section className="mt-8" aria-labelledby="alerts-title" data-panel="alerts">
        <h3 id="alerts-title" className={subheading}>
          Alerts and webhooks
        </h3>
        <p className={lede}>Alert cards stay in the app. Nothing is emailed. Webhooks stay closed when this is off.</p>
        {settings && (
          <>
            <div className="grid gap-2">
              <SwitchRow
                label="Alerts"
                checked={settings.alerts.enabled}
                busy={busy}
                onChange={(value) => void save({ alerts_enabled: value })}
              />
              <SwitchRow
                label="Webhooks"
                checked={settings.webhooks.enabled}
                busy={busy}
                onChange={(value) => void save({ webhooks_enabled: value })}
              />
            </div>
            <dl className="m-0 mt-2 p-0">
              <Fact label="Bantō webhook" value={settings.webhooks.banto} />
              <Fact label="Bantō X webhook" value={settings.webhooks.banto_x} />
            </dl>
          </>
        )}
      </section>

      <section className="mt-8" aria-labelledby="voice-title" data-panel="voice">
        <h3 id="voice-title" className={subheading}>
          Voice
        </h3>
        <p className={lede}>The microphone only fills the box. Audio is not stored.</p>
        {settings && (
          <>
            <SwitchRow
              label="Microphone"
              checked={settings.voice.mic === "on"}
              disabled={!settings.voice.env_enabled}
              busy={busy}
              onChange={(value) => void save({ voice_enabled: value })}
            />
            <dl className="m-0 mt-2 p-0">
              <Fact label="Voxtral" value={settings.voice.voxtral} />
            </dl>
            {settings.voice.detail && <p className={cx(meta, "mt-2")}>{settings.voice.detail}</p>}
          </>
        )}
      </section>

      <section className="mt-8" aria-labelledby="x-limits-title" data-panel="x-limits">
        <h3 id="x-limits-title" className={subheading}>
          X limits
        </h3>
        <p className={lede}>{settings?.x.detail ?? "X stays off until X_ENABLED is set."}</p>
        {settings && (
          <form
            className="mt-2"
            onSubmit={(event) =>
              saveNumbers(event, {
                x_sync_minutes: Number(sync),
                x_daily_cap: Number(daily),
                x_from_max: Number(fromMax),
                x_draft_expiry_days: Number(expiry),
              })
            }
          >
            <NumberField
              id="x-sync"
              label="Sync interval in minutes"
              hint="5 to 1440. The house file still decides whether X is on."
              min={5}
              max={1440}
              value={sync}
              disabled={busy}
              onChange={setSync}
            />
            <NumberField
              id="x-daily"
              label="Daily cap"
              hint="New X lines kept in one house day. 1 to 100."
              min={1}
              max={100}
              value={daily}
              disabled={busy}
              onChange={setDaily}
            />
            <NumberField
              id="x-from"
              label="From X maximum"
              hint="Lines on the From X brief. 1 to 20."
              min={1}
              max={20}
              value={fromMax}
              disabled={busy}
              onChange={setFromMax}
            />
            <NumberField
              id="x-expiry"
              label="Draft expiry in days"
              hint="New drafts only. 1 to 30."
              min={1}
              max={30}
              value={expiry}
              disabled={busy}
              onChange={setExpiry}
            />
            <button type="submit" className={ghost} disabled={busy}>
              Save X limits
            </button>
          </form>
        )}
      </section>

      <section className="mt-8" aria-labelledby="context-title" data-panel="agent-context">
        <h3 id="context-title" className={subheading}>
          Agent context
        </h3>
        <p className={lede}>How much of the log one run may see. Nothing is sent until a run asks.</p>
        {settings && (
          <form
            className="mt-2"
            onSubmit={(event) =>
              saveNumbers(event, {
                context_token_budget: Number(tokens),
                context_memory_limit: Number(memory),
                context_smart_add_days: Number(smartDays),
                context_catch_up_days: Number(catchDays),
              })
            }
          >
            <NumberField
              id="context-tokens"
              label="Context token budget"
              hint="500 to 8000."
              min={500}
              max={8000}
              value={tokens}
              disabled={busy}
              onChange={setTokens}
            />
            <NumberField
              id="context-memory"
              label="Memory lines"
              hint="1 to 10."
              min={1}
              max={10}
              value={memory}
              disabled={busy}
              onChange={setMemory}
            />
            <NumberField
              id="context-smart"
              label="Smart Add days"
              hint="1 to 14."
              min={1}
              max={14}
              value={smartDays}
              disabled={busy}
              onChange={setSmartDays}
            />
            <NumberField
              id="context-catch"
              label="Catch-up days"
              hint="1 to 14. Follow-ups use the same window."
              min={1}
              max={14}
              value={catchDays}
              disabled={busy}
              onChange={setCatchDays}
            />
            <button type="submit" className={ghost} disabled={busy}>
              Save agent context
            </button>
          </form>
        )}
      </section>

      <section className="mt-8" aria-labelledby="docs-title" data-panel="docs">
        <h3 id="docs-title" className={subheading}>
          Docs
        </h3>
        <p className={lede}>Published only when both switches are on, and only behind Cloudflare Access.</p>
        {settings && (
          <p className={cx(kickerMuted, "mt-2")} data-docs={settings.docs.state}>
            <span className={settings.docs.state === "behind access" ? "text-success" : undefined}>
              {settings.docs.state === "behind access"
                ? "Behind Access"
                : settings.docs.state === "not published"
                  ? "Not published"
                  : "Off"}
            </span>
          </p>
        )}
        {settings?.docs.detail && <p className={cx(meta, "mt-2")}>{settings.docs.detail}</p>}
      </section>

      {error && (
        <p className={cx(errorText, "mt-4")} role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}
