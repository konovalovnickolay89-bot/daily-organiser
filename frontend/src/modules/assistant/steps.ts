export const STEP_LABEL = {
  received: "Received.",
  reading: "Reading the house log.",
  calling: "Calling the assistant.",
  done: "Done.",
  failed: "Failed.",
} as const;

export type StepName = keyof typeof STEP_LABEL;

const ORDER: StepName[] = ["received", "reading", "calling", "done", "failed"];

export function noteStep(steps: StepName[], step: string): StepName[] {
  if (!(step in STEP_LABEL)) return steps;
  const name = step as StepName;
  let next = steps.filter((item) => item !== name);
  if (name === "done") next = next.filter((item) => item !== "failed");
  if (name === "failed") next = next.filter((item) => item !== "done");
  next.push(name);
  return next;
}

export function orderedSteps(steps: StepName[]): StepName[] {
  const seen = new Set(steps);
  return ORDER.filter((step) => seen.has(step));
}
