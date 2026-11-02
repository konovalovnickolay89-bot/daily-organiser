import { useEffect, useState } from "react";
import { listTasks } from "../../api/tasks.js";
import { useHouse } from "../../house/HouseContext.jsx";
import { taskMeta } from "../../lib/labels.js";
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
    listTasks({ scope: "today", limit: 5 })
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
      {items === null && !error && <p className="empty">Checking the day…</p>}
      {items?.length === 0 && <p className="empty">Nothing due today.</p>}
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
