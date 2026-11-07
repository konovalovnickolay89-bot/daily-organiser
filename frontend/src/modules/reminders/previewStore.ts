const KEY = "organiser-reminder-preview";

/** Proposed. This browser only. It does not start or stop the assistant. */
export function previewShown(): boolean {
  try {
    return window.localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setPreviewShown(shown: boolean) {
  try {
    window.localStorage.setItem(KEY, shown ? "on" : "off");
  } catch {
    /* The choice holds until reload. */
  }
}
