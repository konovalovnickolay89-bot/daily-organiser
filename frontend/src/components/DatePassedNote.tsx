import { dateHasPassedNote } from "../lib/dates";

type DatePassedNoteProps = {
  dueOn?: string | null;
  houseDate?: string | null;
};

export function DatePassedNote({ dueOn, houseDate }: DatePassedNoteProps) {
  const note = dateHasPassedNote(dueOn, houseDate);
  if (!note) return null;
  return (
    <p className="text-[0.78rem] text-[var(--muted)]" data-note="date-passed">
      {note}
    </p>
  );
}
