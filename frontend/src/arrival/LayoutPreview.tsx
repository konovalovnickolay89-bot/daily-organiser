import { useState } from "react";
import { Rail } from "./Rail";
import { card, cx, ghost, heading, inset, kickerMuted, lede, primary } from "./ui";

const STORAGE = "organiser-layout-preview";

type PreviewSection = {
  id: string;
  title: string;
  count: string;
  summary: string;
  /** Shown on the row even when another section is open. */
  attention?: string;
  primary: string;
  secondary?: string;
  body: string;
};

/** Mock lines only. This is not the live front page and it does not read the house. */
const SECTIONS: PreviewSection[] = [
  {
    id: "brief",
    title: "Brief",
    count: "2",
    summary: "1 due today · 1 overdue",
    attention: "Test data: boiler filters are overdue",
    primary: "Open the brief",
    body: "Test data. The overdue line stays on the overview. The rest of the brief opens here.",
  },
  {
    id: "today",
    title: "Today",
    count: "1",
    summary: "Test data: put the bins out",
    primary: "Add a task",
    body: "Test data. One task is due today. Adding a task is the primary action for this section.",
  },
  {
    id: "proposals",
    title: "Proposed changes",
    count: "1",
    summary: "Test data: oat milk",
    attention: "Test data: oat milk is waiting",
    primary: "Apply",
    secondary: "Not now",
    body: "Test data. The line waits here until Apply. Voice on the live page is unchanged.",
  },
  {
    id: "decisions",
    title: "Decisions",
    count: "1",
    summary: "Test data: advice only",
    primary: "Record decision",
    body: "Test data. Recording the decision does not send, buy, or book.",
  },
  {
    id: "x",
    title: "X",
    count: "Off",
    summary: "Test data: not connected",
    primary: "Connect",
    body: "Test data. X opens in this pane. It does not add another column. The open X pull request is separate.",
  },
];

const ACTIVITY = [
  "Test data: Put the bins out",
  "Test data: Oat milk proposed",
  "Test data: Nothing was sent",
];

/** The dev server is the only caller. App.tsx also requires import.meta.env.DEV. */
export function layoutPreviewQuery(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("layout-preview") === "1";
}

function readOpen(): string {
  try {
    const saved = window.localStorage.getItem(STORAGE);
    if (saved && SECTIONS.some((section) => section.id === saved)) return saved;
  } catch {
    /* A private window keeps the default for this visit. */
  }
  return "brief";
}

function remember(id: string) {
  try {
    window.localStorage.setItem(STORAGE, id);
  } catch {
    /* The choice still holds until reload. */
  }
}

/**
 * Isolated overview and detail. Not mounted unless `?layout-preview=1` in dev.
 * PR 23's X card and its migration are not included.
 */
export function LayoutPreview() {
  const [openId, setOpenId] = useState(readOpen);
  const open = SECTIONS.find((section) => section.id === openId) ?? SECTIONS[0];

  function choose(id: string) {
    setOpenId(id);
    remember(id);
  }

  return (
    <div className="shell flex min-h-screen items-stretch bg-canvas max-[720px]:flex-col" data-theme="evening" data-layout-preview="1">
      <Rail view="home" onView={() => {}} />
      <main className="stage min-w-0 flex-1 outline-none" aria-label="Layout preview">
        <div className="mx-auto w-full max-w-[1280px]">
          <p className="tube-line mb-6 rounded-inset px-6 py-4 text-sm text-cream" role="note">
            Layout preview. Not the live front page. Every line here is test data.
          </p>
          <div className="grid items-start gap-6 min-[900px]:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
            <section className="paper card tube min-w-0 rounded-house p-8 text-[var(--ink)]" aria-labelledby="preview-overview">
              <h1 id="preview-overview" className={heading}>
                House
              </h1>
              <p className={lede}>One section opens on the right. Urgent lines stay in the list.</p>
              <ul className="m-0 grid list-none gap-2 p-0">
                {SECTIONS.map((section) => {
                  const selected = section.id === open.id;
                  return (
                    <li key={section.id}>
                      <button
                        type="button"
                        className={cx(
                          "flex w-full min-h-11 flex-col items-stretch gap-2 rounded-inset px-4 py-2 text-left",
                          selected ? "tube-line bg-accent text-[#1b140c]" : "border-0 bg-transparent text-inherit",
                        )}
                        aria-expanded={selected}
                        aria-controls="layout-detail"
                        onClick={() => choose(section.id)}
                      >
                        <span className="flex items-baseline justify-between gap-4">
                          <span className="text-base font-semibold">{section.title}</span>
                          <span
                            className={cx(
                              "m-0 whitespace-nowrap font-mono text-sm font-medium tabular-nums",
                              selected ? "text-[#1b140c]" : "text-[var(--muted)]",
                            )}
                          >
                            {section.count}
                          </span>
                        </span>
                        <span className={cx("text-sm leading-snug", selected ? "text-[#1b140c]" : "text-[var(--muted)]")}>{section.summary}</span>
                        {section.attention && (
                          <span className={cx("text-sm font-semibold", selected ? "text-[#1b140c]" : "text-accent-ink")}>
                            {section.attention}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
            <section id="layout-detail" className={card} aria-labelledby="layout-detail-title">
              <p className={kickerMuted}>Open section</p>
              <h2 id="layout-detail-title" className={cx(heading, "mt-2")}>
                {open.title}
              </h2>
              <p className={lede}>{open.body}</p>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" className={primary}>
                  {open.primary}
                </button>
                {open.secondary && (
                  <button type="button" className={ghost}>
                    {open.secondary}
                  </button>
                )}
              </div>
              <ol className={`${inset} tube-log mb-0 ml-0 mr-0 mt-8 grid list-none gap-2`} aria-label="Recent activity">
                {ACTIVITY.map((line) => (
                  <li key={line} className="font-mono text-sm leading-normal">
                    {line}
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
