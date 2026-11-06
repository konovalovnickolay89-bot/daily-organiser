import type { ComponentType } from "react";
import { AssistantPane } from "../modules/assistant/AssistantPane";
import { ReasoningPane } from "../modules/assistant/ReasoningPane";
import { MorningBrief } from "../modules/brief/MorningBrief";
import { QuietSuggestion } from "../modules/media/QuietSuggestion";
import { XCards } from "../modules/x/XCards";
import { TodayList } from "../modules/tasks/TodayList";

/**
 * Arrival screen registry.
 *
 * Panels, read by ArrivalShell:
 *   "brief"      — brief card
 *   "today"      — today card (tasks, then the add line)
 *   "reasoning"  — working strip and proposal cards
 *   "corner"     — quiet line under the cards, when the playlist flag is on
 */
export const arrivalModules: Array<{ id: string; panel: string; Component: ComponentType }> = [
  { id: "morning-brief", panel: "brief", Component: MorningBrief },
  { id: "today", panel: "today", Component: TodayList },
  { id: "assistant", panel: "today", Component: AssistantPane },
  { id: "reasoning", panel: "reasoning", Component: ReasoningPane },
  { id: "x-cards", panel: "reasoning", Component: XCards },
  { id: "quiet-media", panel: "corner", Component: QuietSuggestion },
];
