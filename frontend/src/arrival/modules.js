import { ApprovalsPane } from "../modules/approvals/ApprovalsPane.jsx";
import { AssistantPane } from "../modules/assistant/AssistantPane.jsx";
import { MorningBrief } from "../modules/brief/MorningBrief.jsx";
import { QuietSuggestion } from "../modules/media/QuietSuggestion.jsx";
import { TodayList } from "../modules/tasks/TodayList.jsx";

/**
 * Arrival screen registry.
 *
 * Slots, read by ArrivalShell:
 *   "primary"   — left pane (daily needs)
 *   "secondary" — right pane (approvals, proposed changes, today)
 *   "corner"    — quiet, non-dominant
 *
 * A later module is added here and talks to src/api. The shell does not change.
 * Any other slot is rendered under the desk.
 */
export const arrivalModules = [
  { id: "morning-brief", slot: "primary", Component: MorningBrief },
  { id: "approvals", slot: "secondary", Component: ApprovalsPane },
  { id: "assistant", slot: "secondary", Component: AssistantPane },
  { id: "today", slot: "secondary", Component: TodayList },
  { id: "quiet-media", slot: "corner", Component: QuietSuggestion },
];
