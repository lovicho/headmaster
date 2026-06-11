"""Phase 0 gate 0-5: state machine transition rules."""

import pytest

from headmaster.schemas import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidTransitionError,
    TaskState,
    validate_transition,
)

HAPPY_PATH = [
    TaskState.REGISTERED,
    TaskState.CLASSIFIED,
    TaskState.PLANNED,
    TaskState.EXECUTING,
    TaskState.CRITIQUING,
    TaskState.VALIDATED,
    TaskState.PUBLISHING,
    TaskState.ASSIMILATING,
    TaskState.COMPLETED,
]


def test_happy_path_transitions_allowed() -> None:
    for current, target in zip(HAPPY_PATH, HAPPY_PATH[1:], strict=False):
        validate_transition(current, target)


def test_replan_loop_allowed() -> None:
    validate_transition(TaskState.CRITIQUING, TaskState.REPLANNING)
    validate_transition(TaskState.REPLANNING, TaskState.PLANNED)


def test_recovery_loop_allowed() -> None:
    validate_transition(TaskState.EXECUTING, TaskState.RECOVERING)
    validate_transition(TaskState.RECOVERING, TaskState.EXECUTING)


def test_phase_gate_transitions_allowed() -> None:
    # orchestra: phase gate passed -> plan next phase
    validate_transition(TaskState.CRITIQUING, TaskState.PLANNED)
    # human gate: granted -> next phase or final validation
    validate_transition(TaskState.AWAITING_HUMAN_APPROVAL, TaskState.PLANNED)
    validate_transition(TaskState.AWAITING_HUMAN_APPROVAL, TaskState.VALIDATED)


def test_invalid_transition_rejected() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(TaskState.REGISTERED, TaskState.PUBLISHING)


def test_terminal_states_have_no_outgoing() -> None:
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_every_state_covered() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(TaskState)
    for state in TaskState:
        if state not in TERMINAL_STATES:
            assert ALLOWED_TRANSITIONS[state], f"{state} has no outgoing transition"
