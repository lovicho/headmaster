"""EvidenceBundle — claims and provenance objectified; the machine-enforced
form of "No Zero-Shot Invention" (I-B-F proof as data, not prose)."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from headmaster.schemas.common import new_id


class SourceRef(BaseModel):
    source: str
    kind: Literal["file", "web", "rag_asset", "trace", "artifact"]


class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: Literal["factual_assertion", "design_inference"]
    supports: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class IBFProof(BaseModel):
    """Provenance fields verified mechanically by the Critic (1st report proof_format)."""

    imitated_assets: list[str] = Field(default_factory=list)
    benchmarked_references: list[str] = Field(default_factory=list)
    fusion_method: str
    trace_ids: list[str] = Field(default_factory=list)
    artifact_hashes: list[str] = Field(default_factory=list)


class VerifierStatus(StrEnum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    REVISE = "revise"


class EvidenceBundle(BaseModel):
    bundle_id: str = Field(default_factory=lambda: new_id("evb"))
    task_id: str
    ibf_proof: IBFProof | None = None
    claims: list[Claim] = Field(default_factory=list)
    counterevidence: list[Claim] = Field(default_factory=list)
    verifier_status: VerifierStatus = VerifierStatus.PENDING
