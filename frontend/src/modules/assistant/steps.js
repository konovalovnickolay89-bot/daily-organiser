export const STEP_LABEL = {
  received: "Received.",
  reading: "Reading the house log.",
  calling: "Calling the assistant.",
  done: "Done.",
  failed: "Failed.",
};

const ORDER = ["received", "reading", "calling", "done", "failed"];

export function noteStep(steps, step) {
  if (!STEP_LABEL[step]) return steps;
  let next = steps.filter((item) => item !== step);
  if (step === "done") next = next.filter((item) => item !== "failed");
  if (step === "failed") next = next.filter((item) => item !== "done");
  next.push(step);
  return next;
}

export function orderedSteps(steps) {
  const seen = new Set(steps);
  return ORDER.filter((step) => seen.has(step));
}
