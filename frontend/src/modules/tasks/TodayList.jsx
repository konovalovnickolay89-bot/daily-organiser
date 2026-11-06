import { useEffect, useState } from "react";
import { listTasks } from "../../api/tasks";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext.jsx";
import { taskMeta } from "../../lib/labels";
import { TaskEditor } from "./TaskEditor.jsx";
import { TaskRow } from "./TaskRow.jsx";

function taskCount(count) {
  if (count === 1) return "1 task";
  return `${count} tasks`;
}

export function TodayList() {
  const { tick, system } = useHouse();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [taskId, setTaskId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listTasks({ scope: "today", limit: 200 })
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
      <div className="module-head">
        <h2 id="today-title">Today</h2>
        {items && <p className="count">{taskCount(items.length)}</p>}
      </div>
      <p className="lede">Due today, and anything still open from earlier.</p>
      {error && (
        <p className="error" role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <LoadingSkeleton label="Checking the day…" />}
      {items?.length === 0 && <p className="empty">Nothing due today.</p>}
      {items?.length === 200 && <p className="meta">Showing the first 200.</p>}
      {items && items.length > 0 && (
        <ul className="item-list today-list">
          {items.map((task) => (
            <TaskRow
              key={task.id}
              title={task.title}
              meta={taskMeta(task, system?.house_date)}
              onOpen={() => setTaskId(task.id)}
            />
          ))}
        </ul>
      )}
      {taskId && <TaskEditor taskId={taskId} onClose={() => setTaskId(null)} />}
    </section>
  );
}
