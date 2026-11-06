import { cx, meta as metaText, rowTitle } from "../../arrival/ui";

type TaskRowProps = {
  title: string;
  meta?: string | null;
  detail?: string | null;
  onOpen: () => void;
};

/** A task row that opens the editor. The whole row is the control. */
export function TaskRow({ title, meta, detail, onOpen }: TaskRowProps) {
  const label = meta ? `Open ${title}. ${meta}` : `Open ${title}`;

  return (
    <li>
      <button
        type="button"
        className="calm flex min-h-11 w-full items-start justify-between gap-4 rounded-inset border-0 bg-transparent px-4 py-2 text-left text-inherit hover:bg-[rgba(26,22,19,0.05)]"
        onClick={onOpen}
        aria-label={label}
      >
        <span className="flex min-w-0 flex-col gap-2">
          <span className={rowTitle}>{title}</span>
          {meta && <span className={cx(metaText, /\d/.test(meta) && "font-mono tabular-nums")}>{meta}</span>}
          {detail && <span className={metaText}>{detail}</span>}
        </span>
        <span className="shrink-0 text-base font-normal leading-none text-[var(--muted)] group-hover:text-accent-ink" aria-hidden="true">
          ›
        </span>
      </button>
    </li>
  );
}
