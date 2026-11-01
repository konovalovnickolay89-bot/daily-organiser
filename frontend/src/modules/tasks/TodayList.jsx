import { useEffect, useState } from "react";
import { listTasks } from "../../api/tasks.js";
import { useHouse } from "../../house/HouseContext.jsx";
import { taskMeta } from "../../lib/labels.js";

export function TodayList() {
  const { tick, system } = useHouse();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listTasks({ scope: "today", limit: 6 })
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

  return (
    <section className="module today" aria-labelledby="today-title" data-module="today">
      <h2 id="today-title">Today</h2>
      <p className="lede">Due today, and anything still open from earlier.</p>
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <p className="empty">Checking the day…</p>}
      {items?.length === 0 && <p className="empty">Nothing due today.</p>}
      {items && items.length > 0 && (
        <ul className="item-list today-list">
          {items.map((task) => (
            <li key={task.id} className="item">
              <h3>{task.title}</h3>
              <p className="meta">{taskMeta(task, system?.house_date)}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
