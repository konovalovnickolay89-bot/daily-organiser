import { useEffect, useState } from "react";
import { listTasks } from "../../api/tasks";
import type { Task } from "../../api/types";
import { SectionHeader } from "../../arrival/SectionHeader";
import { empty, errorText } from "../../arrival/ui";
import { EmptyState } from "../../components/EmptyState";
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
      <SectionHeader
        id="today-title"
        title="Today"
        note="Due today, and anything still open from earlier."
        meta={items ? taskCount(items.length) : undefined}
      />
      {error && (
        <p className={errorText} role="alert">
          {error.message}
        </p>
      )}
      {items === null && !error && <LoadingSkeleton label="Checking the day…" />}
      {items?.length === 0 && <EmptyState>Nothing due today.</EmptyState>}
      {items?.length === 200 && <p className={empty}>Showing the first 200.</p>}
      {items && items.length > 0 && (
        <ul className="m-0 list-none p-0">
          {items.map((task) => (
            <TaskRow key={task.id} title={task.title} meta={taskMeta(task, system?.house_date)} onOpen={() => setTaskId(task.id)} />
          ))}
        </ul>
      )}
      {taskId && <TaskEditor taskId={taskId} onClose={() => setTaskId(null)} />}
    </section>
  );
}
