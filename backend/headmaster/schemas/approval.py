"""Human-in-the-loop approval contracts."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from headmaster.schemas.common import new_id

ApprovalKind = Literal["publish", "budget_overrun", "phase_gate"]


class ApprovalTicket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: new_id("apv"))
    task_id: str
    kind: ApprovalKind
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    granted: bool
    approver: str
    note: str | None = None
