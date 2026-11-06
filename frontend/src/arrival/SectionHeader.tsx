import type { ReactNode } from "react";
import { count, cx, heading, inset, lede } from "./ui";

type SectionHeaderProps = {
  id: string;
  title: string;
  note?: ReactNode;
  meta?: ReactNode;
  metaClassName?: string;
  divided?: boolean;
};

/**
 * The one section header. Proposed changes and Decisions both use it.
 * When divided, the header uses the same frame as an Advice card, and stays its own box.
 * What the section does stays with the caller.
 */
export function SectionHeader({ id, title, note, meta, metaClassName, divided = false }: SectionHeaderProps) {
  return (
    <div className={divided ? cx("mt-8", inset) : undefined} data-section-header={divided ? "divided" : "plain"}>
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
