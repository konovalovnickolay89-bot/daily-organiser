import { useEffect, useState, type ReactNode } from "react";
import { applyXItem, dismissXItem, listXItems, pollX, postXDraft, type XCard } from "../../api/x";
import { actions, cx, dialog, empty, errorText, ghost, heading, inset, kickerAccent, lede, meta, primary, subheading } from "../../arrival/ui";
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
      <p className={empty}>Nothing is posted until you confirm.</p>
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      <div className={actions}>
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

type XSlots = {
  rows: ReactNode;
  dialog: ReactNode;
  notice: ReactNode;
  error: ReactNode;
  empty: boolean;
  loading: boolean;
};

/**
 * Bookmark and watch cards take Keep or Not now. Keep writes the line into this log.
 * A draft takes Post, then a confirm that shows the stored text. Nothing is posted
 * from this list on its own. `render` places the rows in the one waiting list.
 */
export function XCards({ render }: { render?: (slots: XSlots) => ReactNode }) {
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
  const loading = items === null && !error;

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

  const rows = waiting.map((item) => (
    <li key={item.id} className={inset} data-x-kind={item.kind} data-kind="x">
      <p className={cx(kickerAccent, "mb-2")}>{LABEL[item.kind]}</p>
      <h3 className={subheading}>{item.summary}</h3>
      {item.detail && <p className={cx(meta, "mt-2 [overflow-wrap:anywhere]")}>{item.detail}</p>}
      <div className={actions}>
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
            aria-label={`Keep ${item.summary}`}
            onClick={() => void decide(item, "apply")}
          >
            Keep
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
  ));
  const dialog = posting ? (
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
  ) : null;
  const noticeNode = notice ? <p className={cx(empty, "mb-4")}>{notice}</p> : null;
  const errorNode = error ? (
    <p className={errorText} role="alert">
      {error}
    </p>
  ) : null;
  const slots: XSlots = {
    rows,
    dialog,
    notice: noticeNode,
    error: errorNode,
    empty: !loading && waiting.length === 0 && !error && !notice,
    loading,
  };
  if (render) return render(slots);
  if (loading) return null;
  if (slots.empty) return null;
  return (
    <section className="mt-8" aria-label="From X" data-module="x-cards">
      {noticeNode}
      {errorNode}
      <ul className="m-0 grid list-none gap-4 p-0">{rows}</ul>
      {dialog}
    </section>
  );
}
