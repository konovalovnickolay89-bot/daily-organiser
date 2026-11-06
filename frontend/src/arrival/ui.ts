export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

const control =
  "calm inline-flex min-h-11 min-w-11 items-center justify-center rounded-pill px-6 text-sm font-semibold disabled:cursor-default disabled:opacity-50";

export const primary = `${control} tube-cap bg-accent text-[#1b140c] hover:enabled:bg-accent-deep`;

export const ghost = `${control} tube-line text-[var(--ink)] hover:enabled:bg-[rgba(26,22,19,0.05)]`;

export const pauseButton =
  "calm tube-line inline-flex min-h-11 min-w-11 items-center justify-center rounded-pill bg-canvas px-6 text-sm font-semibold text-cream hover:enabled:bg-[rgba(244,236,223,0.08)] aria-pressed:border-transparent aria-pressed:bg-accent aria-pressed:text-[#1b140c] aria-pressed:shadow-[inset_0_1px_0_rgba(255,244,224,0.75),inset_0_-2px_0_rgba(80,42,12,0.4)] disabled:cursor-default disabled:opacity-50";

/** Choice chip. A small tube, solid brass when chosen. */
export const pill =
  "tube-line relative inline-flex min-h-11 cursor-pointer items-center rounded-pill px-6 text-sm font-semibold has-[:checked]:bg-accent has-[:checked]:text-[#1b140c] focus-within:outline focus-within:outline-2 focus-within:outline-offset-[5px] focus-within:outline-accent-ink";

/** Cream card. Brass tube rim, with room between the type and that rim. */
export const card =
  "paper card tube min-w-0 rounded-house p-12 text-[var(--ink)] max-[720px]:p-8";

/** Inner panel. A quieter tube, and padding so the type clears the rim. */
export const inset = "tube-inset w-full min-w-0 rounded-inset p-6";

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

export const notice = "tube-inset tube-note mb-4 rounded-inset px-6 py-4 text-sm text-[var(--ink)]";

export const fieldInput =
  "tube-well min-h-12 w-full min-w-0 rounded-inset px-6 text-[var(--ink)] placeholder:text-[var(--muted)] disabled:opacity-60";

export const fieldLabel = kickerMuted;

export const fieldStack = "mb-4 flex flex-col gap-2";

export const fieldHint = "text-sm font-normal normal-case tracking-normal text-[var(--muted)]";

export const actions = "mt-4 flex flex-wrap items-center gap-2";

export const dialogActions = "mt-4 flex flex-wrap gap-2 border-t border-[var(--line)] pt-4";

export const dialog =
  "paper tube m-auto max-h-[min(88vh,42rem)] w-[min(26rem,calc(100vw-32px))] overflow-auto rounded-house p-10 text-[var(--ink)] backdrop:bg-[rgba(7,6,5,0.72)]";
