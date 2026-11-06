from enum import Enum


class TaskStatus(str, Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CommitmentStatus(str, Enum):
    open = "open"
    kept = "kept"
    dropped = "dropped"


class EventKind(str, Enum):
    note = "note"
    system = "system"
    approval = "approval"
    task = "task"
    commitment = "commitment"
    brief = "brief"


class ActionMode(str, Enum):
    observe = "observe"
    advise = "advise"
    prepare = "prepare"
    execute = "execute"


class ActionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    skipped = "skipped"


class GreetingReason(str, Enum):
    arrival = "arrival"
    time_of_day = "time_of_day"


class AgentTrigger(str, Enum):
    """Why the Mistral assistant ran. Each value is a rule id in organiser/agent/rules.py."""

    feed = "feed"
    morning_review = "morning_review"
    doing_stalled = "doing_stalled"
    overdue_lingering = "overdue_lingering"
    commitment_due_soon = "commitment_due_soon"


PROACTIVE_TRIGGERS = (
    AgentTrigger.morning_review.value,
    AgentTrigger.doing_stalled.value,
    AgentTrigger.overdue_lingering.value,
    AgentTrigger.commitment_due_soon.value,
)


class ProposalAction(str, Enum):
    """The only changes an applied proposal can make."""

    create_task = "create_task"
    update_task = "update_task"
    create_commitment = "create_commitment"
    update_commitment = "update_commitment"
    add_note = "add_note"
    create_shopping_item = "create_shopping_item"
    remember = "remember"
    forget = "forget"


class ProposalStatus(str, Enum):
    pending = "pending"
    applied = "applied"
    dismissed = "dismissed"
    stale = "stale"


DEFAULT_OWNER = "Nick"

TASK_STATUS_LABELS = {
    TaskStatus.todo.value: "To do",
    TaskStatus.doing.value: "Doing",
    TaskStatus.done.value: "Done",
}

COMMITMENT_STATUS_LABELS = {
    CommitmentStatus.open.value: "Open",
    CommitmentStatus.kept.value: "Kept",
    CommitmentStatus.dropped.value: "Dropped",
}

PRIORITY_LABELS = {
    Priority.low.value: "Low",
    Priority.medium.value: "Medium",
    Priority.high.value: "High",
}

# Approvals record a decision. None of these sentences are followed by a side effect.
DECISION_SUMMARIES = {
    ActionMode.observe.value: "Noted. Nothing further was done.",
    ActionMode.advise.value: "Advice accepted as a note only. Nothing was sent.",
    ActionMode.prepare.value: "Marked to prepare. Nothing was gathered or ordered.",
    ActionMode.execute.value: (
        "Decision recorded. Execute is not wired, so nothing was sent, bought, or changed outside this log."
    ),
}

SKIP_SUMMARY = "Skipped. Nothing was done."
