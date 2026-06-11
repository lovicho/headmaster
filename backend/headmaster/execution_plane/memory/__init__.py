"""Memory fabric — five-layer memory with quarantine and gated consolidation."""

from headmaster.execution_plane.memory.consolidation import (
    PROMOTION_MIN_CONFIDENCE,
    PROMOTION_MIN_REUSE,
    SKILL_MIN_TEST_PASS_RATE,
    eligible_for_promotion,
    promote_episode,
    publish_skill,
)
from headmaster.execution_plane.memory.fabric import MemoryFabric
from headmaster.execution_plane.memory.knowledge_manager import KnowledgeManager

__all__ = [
    "PROMOTION_MIN_CONFIDENCE",
    "PROMOTION_MIN_REUSE",
    "SKILL_MIN_TEST_PASS_RATE",
    "KnowledgeManager",
    "MemoryFabric",
    "eligible_for_promotion",
    "promote_episode",
    "publish_skill",
]
