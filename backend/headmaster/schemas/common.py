"""Shared enums and ID helpers for all Headmaster schemas.

English-Core: every field name and enum value is English; only
client-facing artifacts are rendered in Korean (Korean-Edge).
"""

import uuid
from enum import StrEnum


def new_id(prefix: str) -> str:
    """Generate a prefixed unique id, e.g. ``tsk_3f2a...``.

    MVP uses uuid4 hex; planned migration to UUIDv7 for time-ordering.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class CostTier(StrEnum):
    """Model routing tier — actual model names are resolved by config/models.yaml."""

    MINI = "mini"
    STANDARD = "standard"
    HEAVY = "heavy"


class Language(StrEnum):
    EN = "en"
    KO = "ko"


class MemoryScope(StrEnum):
    """Five-layer memory fabric (2nd report)."""

    STM = "stm"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    SKILL = "skill"
    EVIDENCE = "evidence"
