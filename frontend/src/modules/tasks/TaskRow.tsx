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
    <li className="py-0.5">
      <button
        type="button"
        className="calm flex min-h-11 w-full items-start justify-between gap-3 rounded-house border-0 bg-transparent px-3 py-2.5 text-left text-inherit hover:bg-[rgba(26,22,19,0.05)]"
        onClick={onOpen}
        aria-label={label}
      >
        <span className="flex min-w-0 flex-col gap-px">
          <span className="text-[0.98rem] font-semibold tracking-[-0.011em] text-[var(--ink)] [overflow-wrap:anywhere]">{title}</span>
          {meta && <span className="text-[0.84rem] text-[var(--muted)]">{meta}</span>}
          {detail && <span className="text-[0.9rem] text-[var(--muted)]">{detail}</span>}
        </span>
        <span className="mt-px shrink-0 text-[1.15rem] font-normal leading-none text-[var(--muted)] group-hover:text-accent-ink" aria-hidden="true">
          ›
        </span>
      </button>
    </li>
  );
}
