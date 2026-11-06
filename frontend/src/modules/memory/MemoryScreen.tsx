import { useEffect, useState } from "react";
import { exportMemory, forgetMemory, listMemory, pinMemory, type MemoryItem } from "../../api/memory";
import { errorText, fieldInput, ghost, lede } from "../../arrival/ui";
import { useHouseTick } from "../../house/HouseContext";
import { asError } from "../../lib/errors";

const KIND_LABEL: Record<string, string> = {
  preference: "Preference",
  fact: "Fact",
  routine: "Routine",
};

/**
 * Memory on the Settings card. List, search, pin, and forget.
 * Forget asks once before it deletes. Export is a JSON file in the browser.
 */
export function MemoryScreen() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<MemoryItem[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const tick = useHouseTick();

  useEffect(() => {
    let cancelled = false;
    listMemory(query)
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(asError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [query, tick]);

  async function togglePin(item: MemoryItem) {
    setBusyId(item.id);
    setError(null);
    try {
      const next = await pinMemory(item.id, !item.pinned);
      setItems((current) => current?.map((row) => (row.id === item.id ? next : row)) ?? null);
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function confirmForget(item: MemoryItem) {
    setBusyId(item.id);
    setError(null);
    try {
      await forgetMemory(item.id);
      setItems((current) => current?.filter((row) => row.id !== item.id) ?? null);
      setConfirmId(null);
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function download() {
    setExporting(true);
    setError(null);
    try {
      const data = await exportMemory();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "memory.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(asError(err));
    } finally {
      setExporting(false);
    }
  }

  const rows = items ?? [];
  return (
    <section className="mt-6" aria-labelledby="memory-title" data-screen="memory">
      <h3 id="memory-title" className="serif m-0 text-[1.35rem] font-medium leading-tight tracking-[-0.02em] text-[var(--ink)]">
        Memory
      </h3>
      <p className={lede}>
        Household notes. Write “remember …” or “forget …” in the box. Nothing is saved until Apply. A hotel, a guest, a colleague, or
        work stays out.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        <label className="min-w-0 flex-1">
          <span className="sr-only">Search memory</span>
          <input
            className={fieldInput}
            type="search"
            value={query}
            maxLength={200}
            autoComplete="off"
            placeholder="Search memory"
            aria-label="Search memory"
            onChange={(event) => {
              setConfirmId(null);
              setQuery(event.target.value);
            }}
          />
        </label>
        <button type="button" className={ghost} disabled={exporting} onClick={() => void download()}>
          {exporting ? "Exporting…" : "Export memory"}
        </button>
      </div>
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <p className="text-[0.95rem] text-[var(--muted)]">Loading memory…</p>}
      {items !== null && rows.length === 0 && (
        <p className="text-[0.95rem] text-[var(--muted)]">{query.trim() ? "Nothing matches." : "Nothing is remembered yet."}</p>
      )}
      <ul className="m-0 grid list-none gap-3 p-0">
        {rows.map((item) => {
          const confirming = confirmId === item.id;
          return (
            <li key={item.id} className="rounded-house border border-[var(--line)] px-3 py-3" data-memory={item.id}>
              <p className="m-0 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent-ink">
                {KIND_LABEL[item.kind] ?? item.kind}
                {item.pinned ? " · Pinned" : ""}
              </p>
              <p className="mb-2 mt-1 text-[1.02rem] font-semibold leading-snug text-[var(--ink)] [overflow-wrap:anywhere]">{item.text}</p>
              {confirming ? (
                <div className="flex flex-wrap gap-2">
                  <p className="m-0 min-h-11 basis-full text-[0.95rem] text-[var(--muted)]">Forget this memory? It is removed from the house.</p>
                  <button
                    type="button"
                    className={ghost}
                    disabled={busyId === item.id}
                    onClick={() => void confirmForget(item)}
                  >
                    Forget
                  </button>
                  <button type="button" className={ghost} disabled={busyId === item.id} onClick={() => setConfirmId(null)}>
                    Keep
                  </button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={ghost}
                    aria-pressed={item.pinned}
                    disabled={busyId === item.id}
                    onClick={() => void togglePin(item)}
                  >
                    {item.pinned ? "Unpin" : "Pin"}
                  </button>
                  <button type="button" className={ghost} disabled={busyId === item.id} onClick={() => setConfirmId(item.id)}>
                    Forget
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
