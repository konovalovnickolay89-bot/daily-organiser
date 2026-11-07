const HANDLE = /^[A-Za-z0-9_]{1,15}$/;
const KEYWORD = /^[A-Za-z0-9][A-Za-z0-9 _-]{0,79}$/;

export function watchValueError(kind: "account" | "keyword", value: string): string | null {
  const raw = value.trim().replace(/\s+/g, " ");
  if (!raw) return "Add a watch.";
  if (kind === "account") {
    const handle = raw.startsWith("@") ? raw.slice(1) : raw;
    if (!HANDLE.test(handle)) {
      return "An account is a handle: letters, numbers, and underscores, up to 15.";
    }
    return null;
  }
  if (!KEYWORD.test(raw)) return "A keyword is plain words, up to 80 characters.";
  return null;
}
