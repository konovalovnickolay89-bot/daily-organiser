export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

const control =
  "calm inline-flex min-h-11 min-w-11 items-center justify-center rounded-house px-4 text-sm font-semibold disabled:cursor-default disabled:opacity-50";

export const primary = `${control} border border-transparent bg-accent text-[#1b140c] hover:enabled:bg-accent-deep`;

export const ghost = `${control} border border-[var(--line)] bg-transparent text-[var(--ink)] hover:enabled:bg-[rgba(26,22,19,0.05)]`;

export const pauseButton =
  "calm inline-flex min-h-11 min-w-11 items-center justify-center rounded-house border border-[var(--line-canvas)] bg-transparent px-4 text-sm font-semibold text-cream hover:enabled:bg-[rgba(244,236,223,0.08)] aria-pressed:border-transparent aria-pressed:bg-accent aria-pressed:text-[#1b140c] disabled:cursor-default disabled:opacity-50";

/** Cream card. Radius, border, and padding are the house measure. */
export const card =
  "paper card min-w-0 rounded-house border border-[var(--line-canvas)] bg-card p-8 text-[var(--ink)] shadow-[var(--card-shadow)] max-[720px]:p-4";

/** A card inside a card: same radius and border, one step of padding. */
export const inset = "w-full min-w-0 rounded-house border border-[var(--line)] bg-card p-4";

export const heading =
  "serif m-0 text-[1.75rem] font-medium leading-[1.15] tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]";

export const subheading =
  "serif m-0 text-xl font-medium leading-tight tracking-[-0.02em] text-[var(--ink)] [overflow-wrap:anywhere]";

export const rowTitle = "text-base font-semibold tracking-[-0.011em] text-[var(--ink)] [overflow-wrap:anywhere]";

export const lede = "mb-4 mt-2 text-base leading-normal text-[var(--muted)]";

export const kicker = "m-0 text-xs font-semibold uppercase tracking-[0.16em]";

export const kickerMuted = `${kicker} text-[var(--muted)]`;

export const kickerAccent = `${kicker} text-accent-ink`;

export const meta = "text-sm leading-snug text-[var(--muted)]";

/** Counts, dates, and other figures. */
export const count = "m-0 whitespace-nowrap font-mono text-sm font-medium tabular-nums text-[var(--muted)]";

export const empty = "m-0 text-sm leading-normal text-[var(--muted)]";

export const errorText = "mb-4 text-[var(--danger)]";

export const notice = "mb-4 rounded-house bg-[var(--note)] px-4 py-2 text-sm text-[var(--ink)]";

export const fieldInput =
  "min-h-11 w-full min-w-0 rounded-house border border-[var(--line)] bg-[var(--sunken)] px-4 text-[var(--ink)] placeholder:text-[var(--muted)] disabled:opacity-60";

export const fieldLabel = kickerMuted;

export const fieldStack = "mb-4 flex flex-col gap-2";

export const fieldHint = "text-sm font-normal normal-case tracking-normal text-[var(--muted)]";

export const actions = "mt-4 flex flex-wrap items-center gap-2";

export const dialogActions = "mt-4 flex flex-wrap gap-2 border-t border-[var(--line)] pt-4";

export const dialog =
  "paper m-auto max-h-[min(88vh,42rem)] w-[min(26rem,calc(100vw-32px))] overflow-auto rounded-house border border-[var(--line-card)] bg-card p-6 text-[var(--ink)] shadow-[var(--card-shadow)] backdrop:bg-[rgba(7,6,5,0.72)]";
