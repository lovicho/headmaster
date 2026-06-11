"""Event envelope aligned with CloudEvents 1.0.

The event log is the source of truth (event sourcing): replay means
replaying recorded events, never re-calling the LLM, so state recovery
is deterministic even though models are not.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from headmaster.schemas.common import new_id


class EventType(StrEnum):
    TASK_REGISTERED = "task.registered"
    TASK_CLASSIFIED = "task.classified"
    HARNESS_COMPILED = "harness.compiled"
    PLAN_CREATED = "plan.created"
    AGENT_DISPATCHED = "agent.dispatched"
    MODEL_CALLED = "model.called"
    MODEL_RESPONDED = "model.responded"
    TOOL_CALLED = "tool.called"
    TOOL_RESPONDED = "tool.responded"
    ARTIFACT_PRODUCED = "artifact.produced"
    CRITIQUE_ISSUED = "critique.issued"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    REPLAN_TRIGGERED = "replan.triggered"
    BUDGET_EXCEEDED = "budget.exceeded"
    STATE_CHANGED = "state.changed"
    ARTIFACT_PUBLISHED = "artifact.published"
    KNOWLEDGE_ASSIMILATED = "knowledge.assimilated"
    RECOVERY_STARTED = "recovery.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class Event(BaseModel):
    specversion: str = "1.0"
    id: str = Field(default_factory=lambda: new_id("evt"))
    source: str
    type: EventType
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    subject: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
