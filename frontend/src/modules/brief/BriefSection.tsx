import type { BriefSection as BriefSectionData } from "../../api/brief";
import { cx } from "../../arrival/ui";
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

  return (
    <Disclosure
      className="border-t border-[var(--line)] py-3.5 pb-2.5"
      startOpen={startOpen}
      summary={
        <span className="flex min-h-11 flex-wrap items-baseline gap-2">
          <Chevron />
          <span className={cx("tracking-[-0.011em] text-[var(--ink)]", section.placeholder ? "font-medium text-[var(--muted)]" : "font-semibold")}>
            {section.title}
          </span>
          <span className="ml-auto text-right text-[0.84rem] font-normal text-[var(--muted)] max-[720px]:ml-[18px] max-[720px]:basis-full max-[720px]:text-left">
            {section.placeholder ? "Not connected" : section.summary}
          </span>
        </span>
      }
    >
      {section.placeholder ? (
        <p className="mt-0.5 text-[0.9rem] text-[var(--muted)]">{section.summary}</p>
      ) : section.items.length === 0 ? (
        <p className="mt-0.5 text-[0.9rem] text-[var(--muted)]">{section.summary}</p>
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
              <li key={item.ref ?? item.id ?? item.title} className="py-3 pb-1.5">
                <h3 className="m-0 text-[0.98rem] font-semibold tracking-[-0.011em] text-[var(--ink)] [overflow-wrap:anywhere]">
                  {item.title}
                </h3>
                {item.meta && <p className="mt-0.5 text-[0.84rem] text-[var(--muted)]">{item.meta}</p>}
                {item.detail && <p className="mt-0.5 text-[0.9rem] text-[var(--muted)]">{item.detail}</p>}
              </li>
            ),
          )}
        </ul>
      )}
      {section.footnote && <p className="mt-0.5 text-[0.84rem] text-[var(--muted)]">{section.footnote}</p>}
    </Disclosure>
  );
}
