"""Deterministic state replay from the event log (Phase 1 gate 1-3).

Folds ``state.changed`` events, validating every transition against the
state machine. Identical event logs always produce identical state sequences.
"""

from collections.abc import Iterable

from headmaster.schemas.events import Event, EventType
from headmaster.schemas.states import TaskState, validate_transition


def replay_states(events: Iterable[Event]) -> list[TaskState]:
    """Reconstruct the full state sequence, enforcing transition legality."""
    states = [TaskState.REGISTERED]
    for event in events:
        if event.type is not EventType.STATE_CHANGED:
            continue
        target = TaskState(event.data["to"])
        validate_transition(states[-1], target)
        states.append(target)
    return states


def replay_final_state(events: Iterable[Event]) -> TaskState:
    return replay_states(events)[-1]
