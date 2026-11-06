/** The line on a proposal card when the run used household memory. */
export function usedMemoriesLabel(count?: number | null): string | null {
  if (!count || count < 1) return null;
  if (count === 1) return "Used 1 memory";
  return `Used ${count} memories`;
}
