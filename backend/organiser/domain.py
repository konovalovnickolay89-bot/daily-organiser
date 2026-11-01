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


DEFAULT_OWNER = "Nick"

TASK_STATUS_LABELS = {
    TaskStatus.todo.value: "To do",
    TaskStatus.doing.value: "Doing",
    TaskStatus.done.value: "Done",
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
