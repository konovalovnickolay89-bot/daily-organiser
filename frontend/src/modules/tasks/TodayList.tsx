import { useEffect, useState } from "react";
import { listTasks } from "../../api/tasks";
import type { Task } from "../../api/types";
import { heading, lede } from "../../arrival/ui";
import { LoadingSkeleton } from "../../components/LoadingSkeleton";
import { useHouse } from "../../house/HouseContext";
import { asError } from "../../lib/errors";
import { taskMeta } from "../../lib/labels";
import { TaskEditor } from "./TaskEditor";
import { TaskRow } from "./TaskRow";

function taskCount(count: number) {
  if (count === 1) return "1 task";
  return `${count} tasks`;
}

export function TodayList() {
  const { tick, system } = useHouse();
  const [items, setItems] = useState<Task[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listTasks({ scope: "today", limit: 200 })
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
  }, [tick]);

  return (
    <section className="today" aria-labelledby="today-title" data-module="today">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="today-title" className={heading}>
          Today
        </h2>
        {items && <p className="m-0 whitespace-nowrap text-[0.82rem] font-medium text-[var(--muted)]">{taskCount(items.length)}</p>}
      </div>
      <p className={lede}>Due today, and anything still open from earlier.</p>
      {error && (
        <p className="mb-3 text-[var(--danger)]" role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <LoadingSkeleton label="Checking the day…" />}
      {items?.length === 0 && <p className="text-[0.9rem] text-[var(--muted)]">Nothing due today.</p>}
      {items?.length === 200 && <p className="text-[0.84rem] text-[var(--muted)]">Showing the first 200.</p>}
      {items && items.length > 0 && (
        <ul className="m-0 mt-2 list-none p-0">
          {items.map((task) => (
            <TaskRow key={task.id} title={task.title} meta={taskMeta(task, system?.house_date)} onOpen={() => setTaskId(task.id)} />
          ))}
        </ul>
      )}
      {taskId && <TaskEditor taskId={taskId} onClose={() => setTaskId(null)} />}
    </section>
  );
}
