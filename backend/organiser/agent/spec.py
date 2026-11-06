"""What Mistral's agent builder holds, kept in the repo.

``python -m organiser.agent sync`` sends ``agent_definition()`` to Mistral, and
``show`` prints the same values for pasting into the console. The function
names here must match the handlers in ``functions.py``; a test checks that.
"""

from organiser.config import Settings

AGENT_NAME = "Daily Organiser"
AGENT_DESCRIPTION = "Reads Nick's home log and proposes changes for his tap. Never changes anything itself."

INSTRUCTIONS_TEMPLATE = """\
You are the assistant inside Daily Organiser, Nick's home operations log. You read the log and propose changes. \
Nick applies or dismisses each proposal with a tap. You never change anything yourself.

Each run starts with a brief from the house: the trigger, the house time, your proposal limit, and the items to look at. \
Do the job that trigger names and nothing else.

Triggers
- feed: Nick wrote something. Turn it into proposals: propose_change for a new task or commitment, a date or a status \
move, add_note for a note on an existing item, and create_shopping_item when he is adding something to buy. \
A shop item is a name only: changes.name, nothing else, and no allergen information. Search first. If the item already exists, propose an edit or a note \
instead of a duplicate. When it is a commute or travel to work, propose the trip if it is not already on the log. \
The brief reads the rota and TfL for a commute to Wembley Park. Do not invent disruptions or a live lookup.
- morning_review: look over today's tasks and open commitments in the brief. Propose at most 2 next steps that make the \
day easier: a date for an undated task, a first step for a vague task, a prep task for a commitment due soon, or closing \
something that looks finished.
- doing_stalled, overdue_lingering, commitment_due_soon: one item has gone quiet or is close to its date. Propose exactly \
one fix for that item: mark it done, move it to a realistic date, put it back to to-do, add a first-step or prep task, \
or mark a commitment kept.

Rules
1. Call get_state first. If paused is true, reply "Paused." and stop.
2. Check facts with search_items and get_item before proposing. Never guess an id.
3. Every proposal names one item and one change, with a reason under 20 words.
4. Dates are in {timezone}. Prefer a specific day, today or later. A date that has already passed still becomes a card. Do not drop it.
5. Stop at the proposal limit in the brief.
6. Before each proposal, check that:
   a. it is not already in the log or waiting as a proposal;
   b. it is one concrete step Nick can do, not a vague aim;
   c. the date is realistic: pick a day in next_7_days with fewer than 3 items, and leave full days alone;
   d. it helps today or this week.
   If any check fails, drop it. Fewer, better proposals beat more.
7. Use web search only for a fact Nick asked for or a fact a proposal needs, such as opening hours, a price or a \
collection day. Search for the fact alone. Never put names, addresses or other house details in a query.
8. Home and daily living only. A commute or the journey to work is part of the house. A personal hotel stay is too. \
Hilton, a guest, a colleague, an employer, or a work system is not: propose nothing and reply "Not for the house log."
9. If something is unclear, propose nothing and say in one line what is missing.
10. When a Context block is present, memory.items holds up to 10 household memories for this line. Use them. Do not \
turn a memory into a duplicate task. A postcode or a coordinate is never in that list, and you do not invent one.
11. propose_draft offers one post for X. Nothing is posted until Nick taps Post and confirms. A draft expires after \
7 days. Hilton, a guest, a colleague, an employer, or a work system is never a draft. If X is off, do not call it.

Reply
One or two short lines, plain words, in the voice of a log. For example: "Added 2 proposals: boiler filters (Fri), \
call the council (Mon)." No greeting, no question, no sign-off."""

_DATE = {"type": "string", "description": "A date as YYYY-MM-DD."}

FUNCTIONS: list[dict] = [
    {
        "name": "get_state",
        "description": (
            "House time, whether the house is paused, counts of open work and waiting proposals, and next_7_days: "
            "how many open tasks and commitments fall due on each of the next 7 days. Read only. "
            "Call it first in every run."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_items",
        "description": (
            "Find tasks and commitments by words in the title or detail, by status, or by due-date range. "
            "Read only. Returns at most 20 items with id, kind, title, status, due date, priority and when each "
            "last changed. Open items come first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Words to look for in the title or detail. Leave out to list by the filters only.",
                },
                "kind": {
                    "type": "string",
                    "enum": ["task", "commitment", "any"],
                    "description": "Which records to search. Default any.",
                },
                "status": {
                    "type": "string",
                    "enum": ["todo", "doing", "done", "open", "kept", "dropped"],
                    "description": "todo, doing or done for tasks; open, kept or dropped for commitments. "
                    "Leave out for every status.",
                },
                "due_from": {**_DATE, "description": "Earliest due date, YYYY-MM-DD."},
                "due_to": {**_DATE, "description": "Latest due date, YYYY-MM-DD."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Default 10."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_item",
        "description": (
            "One task or commitment with every field, plus any proposal already waiting for it. Read only. "
            "Use it before proposing a change to an existing item."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["task", "commitment"]},
                "id": {"type": "string", "description": "The item's id from search_items or the brief."},
            },
            "required": ["kind", "id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_change",
        "description": (
            "Put one change on Nick's screen as a card with Apply and Not now. Nothing changes until he taps Apply. "
            "Use it for a new task or commitment, a shop item (create_shopping_item, name only), a new due date, "
            "a status move, or a clearer title or detail. "
            "Never for deleting, changing the owner, or anything outside the house. Refused while the house is "
            "paused, past the proposal limit, for a duplicate, or when a proposal for the "
            "same item is already waiting. A date before today stays on the card."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create_task",
                        "update_task",
                        "create_commitment",
                        "update_commitment",
                        "create_shopping_item",
                    ],
                },
                "id": {
                    "type": "string",
                    "description": "The item's id. Required for update_task and update_commitment. "
                    "Leave out when creating.",
                },
                "changes": {
                    "type": "object",
                    "description": "Only the fields to set.",
                    "properties": {
                        "title": {"type": "string", "maxLength": 200},
                        "name": {
                            "type": "string",
                            "maxLength": 80,
                            "description": "Shopping only. The item name. No allergen information.",
                        },
                        "detail": {"type": "string", "maxLength": 1000},
                        "due_on": {**_DATE, "description": "YYYY-MM-DD. Prefer today or later. A past date stays on the card."},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Tasks only.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["todo", "doing", "done", "open", "kept", "dropped"],
                            "description": "todo, doing or done for tasks; open, kept or dropped for commitments. "
                            "Not for creating.",
                        },
                    },
                    "additionalProperties": False,
                },
                "reason": {
                    "type": "string",
                    "maxLength": 160,
                    "description": "Why, in under 20 words. Shown under the card.",
                },
            },
            "required": ["action", "changes", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_note",
        "description": (
            "Propose a short dated note on an existing task or commitment: a fact Nick gave, or one you found. "
            "Shown as a card. The note is added only if Nick taps Apply. Do not repeat what the item already says."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["task", "commitment"]},
                "id": {"type": "string"},
                "note": {"type": "string", "maxLength": 300},
                "reason": {"type": "string", "maxLength": 160, "description": "Why, in under 20 words."},
            },
            "required": ["kind", "id", "note", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_draft",
        "description": (
            "Propose one post for X as a card. Nothing is posted until Nick taps Post and confirms. "
            "Refused while the house is paused, when X is off, past the proposal limit, or when the text "
            "is Hilton, a guest, a colleague, an employer, or a work system. A draft expires after 7 days."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 280, "description": "The post, in Nick's words."},
                "reason": {"type": "string", "maxLength": 160, "description": "Why, in under 20 words."},
            },
            "required": ["text", "reason"],
            "additionalProperties": False,
        },
    },
]

# Mistral runs these itself. Search is the design doc's web_lookup.
BUILTIN_TOOLS: list[dict] = [{"type": "web_search"}]


def instructions(settings: Settings) -> str:
    return INSTRUCTIONS_TEMPLATE.format(timezone=settings.house_timezone)


def agent_definition(settings: Settings) -> dict:
    """Body for Mistral's create and update agent calls."""
    completion_args: dict = {"temperature": 0.2}
    effort = settings.mistral_reasoning_effort.strip()
    if effort:
        completion_args["reasoning_effort"] = effort
    return {
        "model": settings.mistral_model,
        "name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "instructions": instructions(settings),
        "tools": [*BUILTIN_TOOLS, *({"type": "function", "function": spec} for spec in FUNCTIONS)],
        "completion_args": completion_args,
    }
