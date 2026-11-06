import { useEffect, useState } from "react";
import { applyXItem, dismissXItem, listXItems, pollX, postXDraft, type XCard } from "../../api/x";
import { cx, dialog, errorText, ghost, heading, lede, primary } from "../../arrival/ui";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { useHouseDialog } from "../../lib/dialog";

const LABEL: Record<XCard["kind"], string> = {
  bookmark: "Bookmark",
  watch_match: "Watch",
  draft: "Draft",
};

function stillWaiting(item: XCard, now: number) {
  if (item.kind !== "draft" || !item.expires_at) return true;
  const expires = Date.parse(item.expires_at);
  return Number.isNaN(expires) || expires > now;
}

function ConfirmPost({
  summary,
  busy,
  error,
  onPost,
  onClose,
}: {
  summary: string;
  busy: boolean;
  error: string | null;
  onPost: () => void;
  onClose: () => void;
}) {
  const { dialogRef, requestClose } = useHouseDialog(onClose);
  return (
    <dialog ref={dialogRef} className={dialog} aria-labelledby="x-post-title" data-dialog="x-post">
      <h2 id="x-post-title" className={heading}>
        Post this to X?
      </h2>
      <p className={lede}>{summary}</p>
      <p className="m-0 text-[0.95rem] text-[var(--muted)]">Nothing is posted until you confirm.</p>
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className={primary} disabled={busy} onClick={onPost}>
          Post
        </button>
        <button type="button" className={ghost} disabled={busy} onClick={requestClose}>
          Cancel
        </button>
      </div>
    </dialog>
  );
}

/**
 * Bookmark and watch cards take Apply or Not now. A draft takes Post, then a confirm.
 * Nothing is posted from this list on its own.
 */
export function XCards() {
  const tick = useHouseTick();
  const [items, setItems] = useState<XCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [posting, setPosting] = useState<XCard | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listXItems()
      .then(async (data) => {
        if (!data.enabled) {
          if (!cancelled) setItems([]);
          return;
        }
        await pollX().catch(() => undefined);
        const next = await listXItems();
        if (!cancelled) {
          setItems(next.items);
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

  const now = Date.now();
  const waiting = (items ?? []).filter((item) => stillWaiting(item, now));
  if (items === null && !error) return null;
  if (waiting.length === 0 && !error && !notice) return null;

  async function decide(item: XCard, action: "apply" | "dismiss") {
    setBusyId(item.id);
    setError(null);
    try {
      if (action === "apply") await applyXItem(item.id);
      else await dismissXItem(item.id);
      setItems((current) => (current ?? []).filter((row) => row.id !== item.id));
      setNotice(action === "apply" ? "Kept. Nothing was sent." : "Not now.");
    } catch (err: unknown) {
      setError(asError(err).message);
    } finally {
      setBusyId(null);
    }
  }

  async function confirmPost() {
    if (!posting) return;
    setBusyId(posting.id);
    setPostError(null);
    try {
      await postXDraft(posting.id);
      setItems((current) => (current ?? []).filter((row) => row.id !== posting.id));
      setPosting(null);
      setNotice("Posted.");
    } catch (err: unknown) {
      setPostError(asError(err).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="mt-6" aria-label="From X" data-module="x-cards">
      {notice && <p className="mb-3 text-[0.9rem] text-[var(--muted)]">{notice}</p>}
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      <ul className="m-0 grid list-none gap-3 p-0">
        {waiting.map((item) => (
          <li
            key={item.id}
            className="w-full min-w-0 rounded-house border border-[var(--line)] bg-card px-4 pb-3.5 pt-4"
            data-x-kind={item.kind}
          >
            <p className="mb-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-ink">{LABEL[item.kind]}</p>
            <h3 className="serif m-0 text-[1.2rem] font-medium leading-[1.25] tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]">
              {item.summary}
            </h3>
            {item.detail && <p className="mt-2 text-[0.9rem] leading-snug text-[var(--muted)] [overflow-wrap:anywhere]">{item.detail}</p>}
            <div className="mt-3.5 flex flex-wrap items-center gap-x-2.5 gap-y-2">
              {item.kind === "draft" ? (
                <button
                  type="button"
                  className={primary}
                  disabled={busyId === item.id}
                  aria-label={`Post ${item.summary}`}
                  onClick={() => setPosting(item)}
                >
                  Post
                </button>
              ) : (
                <button
                  type="button"
                  className={primary}
                  disabled={busyId === item.id}
                  aria-label={`Apply ${item.summary}`}
                  onClick={() => void decide(item, "apply")}
                >
                  Apply
                </button>
              )}
              <button
                type="button"
                className={cx(ghost, "font-medium text-[var(--muted)]")}
                disabled={busyId === item.id}
                aria-label={`Not now ${item.summary}`}
                onClick={() => void decide(item, "dismiss")}
              >
                Not now
              </button>
            </div>
          </li>
        ))}
      </ul>
      {posting && (
        <ConfirmPost
          summary={posting.summary}
          busy={busyId === posting.id}
          error={postError}
          onPost={() => void confirmPost()}
          onClose={() => {
            setPosting(null);
            setPostError(null);
          }}
        />
      )}
    </section>
  );
}
