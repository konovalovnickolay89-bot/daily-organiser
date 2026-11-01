import { ApprovalsPane } from "../modules/approvals/ApprovalsPane.jsx";
import { MorningBrief } from "../modules/brief/MorningBrief.jsx";
import { QuietSuggestion } from "../modules/media/QuietSuggestion.jsx";
import { TodayList } from "../modules/tasks/TodayList.jsx";

/**
 * Arrival screen registry.
 *
 * Slots: "primary" (left), "secondary" (right), "corner".
 * A later module is added here and talks to src/api. The shell does not need a rewrite.
 * Any other slot is rendered under the panes.
 */
export const arrivalModules = [
  { id: "morning-brief", slot: "primary", Component: MorningBrief },
  { id: "approvals", slot: "secondary", Component: ApprovalsPane },
  { id: "today", slot: "secondary", Component: TodayList },
  { id: "quiet-media", slot: "corner", Component: QuietSuggestion },
];
