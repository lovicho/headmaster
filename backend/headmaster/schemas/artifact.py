"""Artifact — published deliverable with provenance links (3rd report state unit)."""

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from headmaster.schemas.common import new_id


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("art"))
    task_id: str
    produced_by: str
    format: str
    content: str
    content_hash: str
    evidence_bundle_id: str
    critique_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
