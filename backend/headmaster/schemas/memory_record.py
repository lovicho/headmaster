"""MemoryRecord — single record of the five-layer memory fabric (2nd report).

Failed-verification records are quarantined, never discarded; promotion to
semantic/skill layers is gated (see plan/02 section 7).
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from headmaster.schemas.common import MemoryScope, new_id


class DecayPolicy(StrEnum):
    REINFORCE_ON_REUSE = "reinforce_on_reuse"
    FIXED_TTL = "fixed_ttl"
    IMMUTABLE = "immutable"


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("mem"))
    scope: MemoryScope
    task_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str
    embedding_ref: str | None = None
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    decay_policy: DecayPolicy = DecayPolicy.REINFORCE_ON_REUSE
    source_refs: list[str] = Field(default_factory=list)
    quarantine: bool = False
    reuse_count: int = Field(default=0, ge=0)
