const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

/** A short note when a due date is before the house date. Blank otherwise. */
export function dateHasPassedNote(dueOn?: string | null, houseDate?: string | null): string {
  if (!dueOn || !houseDate) return "";
  const due = dueOn.slice(0, 10);
  const house = houseDate.slice(0, 10);
  if (!ISO_DAY.test(due) || !ISO_DAY.test(house)) return "";
  return due < house ? "That date has passed." : "";
}
