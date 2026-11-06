import { meta } from "../arrival/ui";
import { dateHasPassedNote } from "../lib/dates";

type DatePassedNoteProps = {
  dueOn?: string | null;
  houseDate?: string | null;
};

export function DatePassedNote({ dueOn, houseDate }: DatePassedNoteProps) {
  const note = dateHasPassedNote(dueOn, houseDate);
  if (!note) return null;
  return (
    <p className={meta} data-note="date-passed">
      {note}
    </p>
  );
}
