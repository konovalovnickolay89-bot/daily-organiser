import { useEffect, useState, type KeyboardEvent } from "react";
import { getAgent } from "../api/agent";
import { listApprovals } from "../api/approvals";
import { getMorningBrief, type MorningBrief as Brief } from "../api/brief";
import { getCommutePlan, type CommutePlan } from "../api/commute";
import { getLineStatus, type LineStatus } from "../api/lines";
import { listTasks } from "../api/tasks";
import type { Proposal } from "../api/types";
import { listXItems } from "../api/x";
import { useHouse } from "../house/HouseContext";
import { asError } from "../lib/errors";
import { AssistantPane } from "../modules/assistant/AssistantPane";
import { ReasoningPane } from "../modules/assistant/ReasoningPane";
import { MorningBrief } from "../modules/brief/MorningBrief";
import { CommuteDetail, commuteOverview } from "../modules/commute/CommutePlan";
import { LineStatusDetail, lineOverview } from "../modules/lines/LineStatusPanel";
import { TodayList } from "../modules/tasks/TodayList";
import { XCards } from "../modules/x/XCards";
import { card, cx, heading, lede } from "./ui";

const STORAGE = "organiser-home-open";

const SECTIONS = ["brief", "commute", "lines", "today", "proposals", "decisions"] as const;
type SectionId = (typeof SECTIONS)[number];

type Row = {
  id: SectionId;
  title: string;
  count: string;
  summary: string;
  urgent: string | null;
};

const EMPTY: Record<SectionId, Row> = {
  brief: { id: "brief", title: "Brief", count: "…", summary: "Checking the brief…", urgent: null },
  commute: { id: "commute", title: "Commute", count: "…", summary: "Checking the commute…", urgent: null },
  lines: { id: "lines", title: "Lines", count: "…", summary: "Checking line status…", urgent: null },
  today: { id: "today", title: "Today", count: "…", summary: "Checking today…", urgent: null },
  proposals: { id: "proposals", title: "Proposed changes", count: "…", summary: "Checking the line…", urgent: null },
  decisions: { id: "decisions", title: "Decisions", count: "…", summary: "Checking decisions…", urgent: null },
};

function readOpen(): SectionId {
  try {
    const saved = window.localStorage.getItem(STORAGE);
    if (saved && (SECTIONS as readonly string[]).includes(saved)) return saved as SectionId;
  } catch {
    /* This visit uses the default. */
  }
  return "brief";
}

function remember(id: SectionId) {
  try {
    window.localStorage.setItem(STORAGE, id);
  } catch {
    /* The choice still holds until reload. */
  }
}

function briefRow(brief: Brief): Row {
  const tasks = brief.sections.find((section) => section.key === "tasks");
  const overdue = (tasks?.items ?? []).filter((item) => (item.meta ?? "").toLowerCase().includes("overdue"));
  return {
    id: "brief",
    title: "Brief",
    count: String(tasks?.items.length ?? 0),
    summary: tasks?.summary || "Daily needs from the house log.",
    urgent: overdue[0]?.title ? `Overdue: ${overdue[0].title}` : null,
  };
}

/**
 * Home. A compact list and one wide pane. Not a centred strip of three columns.
 * X stays inside Decisions. The open section is remembered on this browser.
 */
export function HomeBoard() {
  const { tick } = useHouse();
  const [open, setOpen] = useState<SectionId>(readOpen);
  const [rows, setRows] = useState<Record<SectionId, Row>>(EMPTY);
  const [commute, setCommute] = useState<CommutePlan | null>(null);
  const [commuteError, setCommuteError] = useState<Error | null>(null);
  const [lines, setLines] = useState<LineStatus | null>(null);
  const [linesError, setLinesError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [brief, tasks, agent, approvals, x, commuteResult, lineResult] = await Promise.all([
        getMorningBrief().catch(() => null),
        listTasks({ scope: "today", limit: 200 }).catch(() => null),
        getAgent().catch(() => null),
        listApprovals("pending").catch(() => null),
        listXItems().catch(() => null),
        getCommutePlan()
          .then((status) => ({ status, error: null as Error | null }))
          .catch((err: unknown) => ({ status: null as CommutePlan | null, error: asError(err) })),
        getLineStatus()
          .then((status) => ({ status, error: null as Error | null }))
          .catch((err: unknown) => ({ status: null as LineStatus | null, error: asError(err) })),
      ]);
      if (cancelled) return;
      setCommute(commuteResult.status);
      setCommuteError(commuteResult.error);
      setLines(lineResult.status);
      setLinesError(lineResult.error);
      const next = { ...EMPTY };
      if (brief) next.brief = briefRow(brief);
      else next.brief = { ...EMPTY.brief, count: "—", summary: "The brief could not be read." };
      const trip = commuteOverview(commuteResult.status, commuteResult.error);
      next.commute = { id: "commute", title: "Commute", ...trip };
      const linesRow = lineOverview(lineResult.status, lineResult.error);
      next.lines = { id: "lines", title: "Lines", ...linesRow };
      if (tasks) {
        const first = tasks.items[0];
        next.today = {
          id: "today",
          title: "Today",
          count: String(tasks.items.length),
          summary: tasks.items.length === 0 ? "Nothing due today." : `${tasks.items.length} on today`,
          urgent: first ? first.title : null,
        };
      } else {
        next.today = { ...EMPTY.today, count: "—", summary: "Today could not be read." };
      }
      const proposals: Proposal[] = agent?.proposals ?? [];
      if (!agent) {
        next.proposals = { ...EMPTY.proposals, count: "—", summary: "The line could not be read." };
      } else if (!agent.enabled) {
        next.proposals = { id: "proposals", title: "Proposed changes", count: "Off", summary: "The assistant is off.", urgent: null };
      } else if (agent.reachable === false) {
        next.proposals = { id: "proposals", title: "Proposed changes", count: "—", summary: "The assistant is down.", urgent: null };
      } else {
        next.proposals = {
          id: "proposals",
          title: "Proposed changes",
          count: String(proposals.length),
          summary: proposals.length === 0 ? "Nothing is waiting on the line." : `${proposals.length} waiting`,
          urgent: proposals[0]?.summary ?? null,
        };
      }
      const waiting = (approvals?.items.length ?? 0) + proposals.length;
      const xCount = x?.enabled ? x.items.length : 0;
      const urgent = approvals?.items[0]?.title || proposals[0]?.summary || (x?.items[0]?.summary ?? null);
      const bits = [waiting === 0 ? "Nothing is waiting." : `${waiting} waiting`];
      if (xCount > 0) bits.push(`${xCount} from X`);
      next.decisions = {
        id: "decisions",
        title: "Decisions",
        count: String(waiting + xCount),
        summary: bits.join(" · "),
        urgent: waiting + xCount > 0 ? urgent : null,
      };
      if (!approvals && !agent) {
        next.decisions = { ...EMPTY.decisions, count: "—", summary: "Decisions could not be read." };
      }
      setRows(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [tick]);

  function choose(id: SectionId) {
    setOpen(id);
    remember(id);
  }

  function onKey(event: KeyboardEvent<HTMLElement>) {
    const index = SECTIONS.indexOf(open);
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const next = event.key === "ArrowDown" ? Math.min(index + 1, SECTIONS.length - 1) : Math.max(index - 1, 0);
    choose(SECTIONS[next]);
    const button = event.currentTarget.querySelector<HTMLButtonElement>(`[data-home-section='${SECTIONS[next]}']`);
    button?.focus();
  }

  return (
    <div data-home-board className="mt-10 grid items-start gap-6 min-[900px]:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)]">
      <section className={card} aria-labelledby="home-overview" onKeyDown={onKey}>
        <h2 id="home-overview" className={heading}>
          House
        </h2>
        <p className={lede}>Open one section. Urgent lines stay in this list.</p>
        <ul className="m-0 grid list-none gap-2 p-0">
          {SECTIONS.map((id) => {
            const row = rows[id];
            const selected = id === open;
            return (
              <li key={id}>
                <button
                  type="button"
                  data-home-section={id}
                  className={cx(
                    "flex w-full min-h-11 flex-col items-stretch gap-2 rounded-inset px-4 py-4 text-left",
                    selected ? "tube-line bg-accent text-[#1b140c]" : "border-0 bg-transparent text-inherit",
                  )}
                  aria-expanded={selected}
                  aria-controls="home-detail"
                  onClick={() => choose(id)}
                >
                  <span className="flex items-baseline justify-between gap-4">
                    <span className="text-base font-semibold">{row.title}</span>
                    <span
                      className={cx(
                        "m-0 whitespace-nowrap font-mono text-sm font-medium tabular-nums",
                        selected ? "text-[#1b140c]" : "text-[var(--muted)]",
                      )}
                    >
                      {row.count}
                    </span>
                  </span>
                  <span className={cx("text-sm leading-snug", selected ? "text-[#1b140c]" : "text-[var(--muted)]")}>{row.summary}</span>
                  {row.urgent && (
                    <span className={cx("text-sm font-semibold", selected ? "text-[#1b140c]" : "text-accent-ink")}>{row.urgent}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section id="home-detail" className={card}>
        {open === "brief" && <MorningBrief />}
        {open === "commute" && <CommuteDetail plan={commute} error={commuteError} />}
        {open === "lines" && <LineStatusDetail status={lines} error={linesError} />}
        {open === "today" && <TodayList />}
        {open === "proposals" && <AssistantPane />}
        {open === "decisions" && (
          <div className="grid gap-6">
            <ReasoningPane />
            <XCards />
          </div>
        )}
      </section>
    </div>
  );
}
