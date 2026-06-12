"""CritiqueReport — verdict of the Critic gate.

Backward compatible with the v8 Critic output schema: a raw v8 example JSON
must validate unmodified (Phase 0 gate 0-2). 3rd-report findings are an
optional extension.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from headmaster.schemas.common import new_id
from headmaster.schemas.rejection_taxonomy import RejectionCategory, RejectionCode


class CritiqueStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerificationDetails(BaseModel):
    imitation_check: str
    benchmark_check: str
    fusion_coherence: str


class Finding(BaseModel):
    code: RejectionCode | None = None
    category: RejectionCategory | None = None
    issue_type: Literal[
        "missing_evidence",
        "logic_gap",
        "policy_violation",
        "format_error",
        "zero_shot_invention",
    ]
    severity: Literal["minor", "moderate", "critical"]
    description: str
    proposed_fix: str | None = None
    operator_summary: str | None = None
    retryable: bool = True
    requires_human_approval: bool = False


class CritiqueReport(BaseModel):
    critique_id: str = Field(default_factory=lambda: new_id("crt"))
    task_id: str | None = None
    target_agent: str
    status: CritiqueStatus
    zero_shot_detected: bool
    verification_details: VerificationDetails
    findings: list[Finding] = Field(default_factory=list)
    mandatory_revisions: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    requires_replan: bool = False

    @property
    def accepted(self) -> bool:
        return self.status is CritiqueStatus.APPROVED
