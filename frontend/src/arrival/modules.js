import { ApprovalsPane } from "../modules/approvals/ApprovalsPane.jsx";
import { AssistantPane } from "../modules/assistant/AssistantPane.jsx";
import { ReasoningPane } from "../modules/assistant/ReasoningPane.jsx";
import { MorningBrief } from "../modules/brief/MorningBrief.jsx";
import { QuietSuggestion } from "../modules/media/QuietSuggestion.jsx";
import { TodayList } from "../modules/tasks/TodayList.jsx";

/**
 * Arrival screen registry.
 *
 * Panels, read by ArrivalShell:
 *   "brief"      — brief card
 *   "approvals"  — approvals card
 *   "today"      — today card (tasks, then the add line)
 *   "reasoning"  — working strip and proposal cards
 *   "corner"     — quiet line under the cards
 *
 * A later module is added here and talks to src/api.
 * Any other panel is rendered under the cards.
 */
export const arrivalModules = [
  { id: "morning-brief", panel: "brief", Component: MorningBrief },
  { id: "approvals", panel: "approvals", Component: ApprovalsPane },
  { id: "today", panel: "today", Component: TodayList },
  { id: "assistant", panel: "today", Component: AssistantPane },
  { id: "reasoning", panel: "reasoning", Component: ReasoningPane },
  { id: "quiet-media", panel: "corner", Component: QuietSuggestion },
];
