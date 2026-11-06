import type { ReactNode } from "react";
import { count, cx, heading, lede } from "./ui";

type SectionHeaderProps = {
  id: string;
  title: string;
  note?: ReactNode;
  meta?: ReactNode;
  metaClassName?: string;
  divided?: boolean;
};

/**
 * The one section header. Proposed changes and Decisions both use it,
 * including the rule when the section sits under something else.
 * What the section does stays with the caller.
 */
export function SectionHeader({ id, title, note, meta, metaClassName, divided = false }: SectionHeaderProps) {
  return (
    <div className={divided ? "mt-8 border-t border-[var(--line)] pt-6" : undefined} data-section-header={divided ? "divided" : "plain"}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 id={id} className={heading}>
          {title}
        </h2>
        {meta != null && meta !== "" && <p className={cx(count, metaClassName)}>{meta}</p>}
      </div>
      {note != null && note !== "" && <p className={lede}>{note}</p>}
    </div>
  );
}
