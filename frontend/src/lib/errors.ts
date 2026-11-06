export function asError(err: unknown): Error {
  if (err instanceof Error) return err;
  return new Error("The house log could not be reached.");
}
