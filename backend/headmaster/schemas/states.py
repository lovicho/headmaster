"""Task state machine (3rd report). Critiquing/Replanning are first-class,
traceable states — not internal model thoughts."""

from enum import StrEnum


class TaskState(StrEnum):
    REGISTERED = "registered"
    CLASSIFIED = "classified"
    PLANNED = "planned"
    EXECUTING = "executing"
    AWAITING_TOOL = "awaiting_tool"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    CRITIQUING = "critiquing"
    REPLANNING = "replanning"
    VALIDATED = "validated"
    PUBLISHING = "publishing"
    ASSIMILATING = "assimilating"
    COMPLETED = "completed"
    RECOVERING = "recovering"
    FAILED = "failed"


TERMINAL_STATES: frozenset[TaskState] = frozenset({TaskState.COMPLETED, TaskState.FAILED})

ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.REGISTERED: frozenset({TaskState.CLASSIFIED, TaskState.FAILED}),
    TaskState.CLASSIFIED: frozenset({TaskState.PLANNED, TaskState.FAILED}),
    TaskState.PLANNED: frozenset({TaskState.EXECUTING, TaskState.FAILED}),
    TaskState.EXECUTING: frozenset(
        {
            TaskState.AWAITING_TOOL,
            TaskState.AWAITING_HUMAN_APPROVAL,
            TaskState.CRITIQUING,
            TaskState.RECOVERING,
            TaskState.FAILED,
        }
    ),
    TaskState.AWAITING_TOOL: frozenset(
        {TaskState.EXECUTING, TaskState.RECOVERING, TaskState.FAILED}
    ),
    TaskState.AWAITING_HUMAN_APPROVAL: frozenset(
        {TaskState.EXECUTING, TaskState.REPLANNING, TaskState.FAILED}
    ),
    TaskState.CRITIQUING: frozenset(
        {
            TaskState.VALIDATED,
            TaskState.REPLANNING,
            TaskState.AWAITING_HUMAN_APPROVAL,
            TaskState.FAILED,
        }
    ),
    TaskState.REPLANNING: frozenset({TaskState.PLANNED, TaskState.FAILED}),
    TaskState.VALIDATED: frozenset({TaskState.PUBLISHING, TaskState.FAILED}),
    TaskState.PUBLISHING: frozenset({TaskState.ASSIMILATING, TaskState.FAILED}),
    TaskState.ASSIMILATING: frozenset({TaskState.COMPLETED, TaskState.FAILED}),
    TaskState.RECOVERING: frozenset({TaskState.EXECUTING, TaskState.FAILED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
}


class InvalidTransitionError(Exception):
    def __init__(self, current: TaskState, target: TaskState) -> None:
        super().__init__(f"invalid transition: {current} -> {target}")
        self.current = current
        self.target = target


def validate_transition(current: TaskState, target: TaskState) -> None:
    """Raise InvalidTransitionError unless current -> target is allowed."""
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
