import { useEffect, useState } from "react";
import { approveRequest, listApprovals, skipRequest } from "../../api/approvals.js";
import { useHouse } from "../../house/HouseContext.jsx";
import { MODE_LABELS } from "../../lib/labels.js";

function waitingLabel(count) {
  if (count === 0) return "None waiting";
  if (count === 1) return "1 waiting";
  return `${count} waiting`;
}

export function ApprovalsPane() {
  const { tick, refresh, system } = useHouse();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [pendingId, setPendingId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listApprovals("pending")
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  async function decide(id, action) {
    setPendingId(id);
    setError(null);
    try {
      const result = action === "approve" ? await approveRequest(id) : await skipRequest(id);
      setNotice(result.effect?.summary || "Decision recorded. Nothing left the house.");
      refresh();
    } catch (err) {
      setError(err);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <section className="module approvals" aria-labelledby="approvals-title" data-module="approvals">
      <div className="module-head">
        <h2 id="approvals-title">Pending approvals</h2>
        {items && <p className="count">{waitingLabel(items.length)}</p>}
      </div>
      <p className="lede">Approve or skip. Nothing here sends, buys, or books.</p>
      {system?.paused && (
        <p className="status-note">The house is paused. A decision is only written to the log.</p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <p className="empty">Looking for decisions…</p>}
      {items?.length === 0 && <p className="empty">Nothing is waiting.</p>}
      <ul className="approval-list">
        {items?.map((item) => (
          <li key={item.id} className="approval">
            <p className="mode">{MODE_LABELS[item.mode] ?? item.mode}</p>
            <h3>{item.title}</h3>
            {item.detail && <p>{item.detail}</p>}
            <p className="meta">{item.owner}</p>
            {item.mode === "execute" && (
              <p className="stub">Approving records the decision only. Nothing is sent.</p>
            )}
            <div className="actions">
              <button
                type="button"
                className="primary"
                disabled={pendingId === item.id}
                onClick={() => decide(item.id, "approve")}
              >
                Approve
              </button>
              <button
                type="button"
                className="ghost"
                disabled={pendingId === item.id}
                onClick={() => decide(item.id, "skip")}
              >
                Skip
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
