export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

const control =
  "calm inline-flex min-h-11 min-w-11 items-center justify-center rounded-house px-3.5 text-[0.9rem] font-semibold disabled:cursor-default disabled:opacity-50";

export const primary = `${control} border border-transparent bg-accent text-[#1b140c] hover:enabled:bg-accent-deep`;

export const ghost = `${control} border border-[var(--line)] bg-transparent text-[var(--ink)] hover:enabled:bg-[rgba(26,22,19,0.05)]`;

export const pauseButton =
  "calm inline-flex min-h-11 min-w-11 items-center justify-center rounded-house border border-[var(--line-canvas)] bg-transparent px-3.5 text-[0.86rem] font-semibold text-cream hover:enabled:bg-[rgba(244,236,223,0.08)] aria-pressed:border-transparent aria-pressed:bg-accent aria-pressed:text-[#1b140c] disabled:cursor-default disabled:opacity-50";

export const card =
  "paper card min-w-0 rounded-house bg-card px-[30px] pb-[22px] pt-7 text-[var(--ink)] shadow-[var(--card-shadow)] max-[720px]:px-[18px] max-[720px]:pb-4 max-[720px]:pt-[22px]";

export const heading =
  "serif m-0 text-[1.7rem] font-medium leading-[1.15] tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]";

export const lede = "mb-4 mt-2 text-[0.95rem] leading-normal text-[var(--muted)]";

export const errorText = "mb-3 text-[var(--danger)]";

export const notice =
  "mb-3 rounded-house bg-[var(--note)] px-3 py-2.5 text-[0.9rem] text-[var(--ink)]";

export const fieldInput =
  "min-h-11 w-full min-w-0 rounded-house border border-[var(--line)] bg-[var(--sunken)] px-3 text-[var(--ink)] placeholder:text-[var(--muted)] disabled:opacity-60";

export const fieldLabel = "text-[0.72rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]";

export const dialog =
  "paper m-auto max-h-[min(88vh,42rem)] w-[min(26.5rem,calc(100vw-28px))] overflow-auto rounded-house border border-[var(--line-card)] bg-card px-[22px] pb-4 pt-[22px] text-[var(--ink)] shadow-[0_28px_70px_rgba(0,0,0,0.45)] backdrop:bg-[rgba(7,6,5,0.72)]";
