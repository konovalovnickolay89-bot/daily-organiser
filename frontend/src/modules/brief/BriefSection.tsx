import type { BriefSection as BriefSectionData } from "../../api/brief";
import { cx, empty, meta, rowTitle } from "../../arrival/ui";
import { TaskRow } from "../tasks/TaskRow";
import { Chevron, Disclosure } from "./Disclosure";

type BriefSectionProps = {
  section: BriefSectionData;
  startOpen?: boolean;
  onOpenTask?: (id: string) => void;
  onOpenCommitment?: (id: string) => void;
};

export function BriefSection({ section, startOpen = false, onOpenTask, onOpenCommitment }: BriefSectionProps) {
  const tasksOpen = section.key === "tasks" && typeof onOpenTask === "function";
  const commitmentsOpen = section.key === "commitments" && typeof onOpenCommitment === "function";
  const openItem = tasksOpen ? onOpenTask : commitmentsOpen ? onOpenCommitment : null;
  const aside = section.placeholder ? "Not connected" : section.summary;
  const figures = /\d/.test(aside);

  return (
    <Disclosure
      className="border-t border-[var(--line)] py-4"
      startOpen={startOpen}
      summary={
        <span className="flex min-h-11 flex-wrap items-baseline gap-2">
          <Chevron />
          <span className={cx("tracking-[-0.011em] text-[var(--ink)]", section.placeholder ? "font-medium text-[var(--muted)]" : "font-semibold")}>
            {section.title}
          </span>
          <span
            className={cx(
              "ml-auto text-right text-sm font-normal text-[var(--muted)] max-[720px]:ml-4 max-[720px]:basis-full max-[720px]:text-left",
              figures && "font-mono tabular-nums",
            )}
          >
            {aside}
          </span>
        </span>
      }
    >
      {section.placeholder ? (
        <p className={cx(empty, "mt-2")}>{section.summary}</p>
      ) : section.items.length === 0 ? (
        <p className={cx(empty, "mt-2")}>{section.summary}</p>
      ) : (
        <ul className="m-0 mt-2 list-none p-0">
          {section.items.map((item) =>
            openItem && item.id ? (
              <TaskRow
                key={item.id}
                title={item.title}
                meta={item.meta}
                detail={item.detail}
                onOpen={() => openItem(item.id as string)}
              />
            ) : (
              <li key={item.ref ?? item.id ?? item.title} className="py-2">
                <h3 className={rowTitle}>{item.title}</h3>
                {item.meta && <p className={cx(meta, "mt-2", /\d/.test(item.meta) && "font-mono tabular-nums")}>{item.meta}</p>}
                {item.detail && <p className={cx(meta, "mt-2")}>{item.detail}</p>}
              </li>
            ),
          )}
        </ul>
      )}
      {section.footnote && <p className={cx(meta, "mt-2")}>{section.footnote}</p>}
    </Disclosure>
  );
}
