"""Gated consolidation (2nd report algorithm).

Episodic -> semantic promotion only after repeated reuse with high
confidence; skills publish only above a test-pass-rate floor. Quarantined
records never promote. Contradiction detection against existing semantic
facts is a later-phase extension.
"""

from headmaster.execution_plane.memory.fabric import MemoryFabric
from headmaster.schemas.common import MemoryScope
from headmaster.schemas.memory_record import MemoryRecord

PROMOTION_MIN_REUSE = 2
PROMOTION_MIN_CONFIDENCE = 0.85
SKILL_MIN_TEST_PASS_RATE = 0.9


def eligible_for_promotion(record: MemoryRecord) -> bool:
    return (
        record.scope is MemoryScope.EPISODIC
        and not record.quarantine
        and record.reuse_count >= PROMOTION_MIN_REUSE
        and record.confidence >= PROMOTION_MIN_CONFIDENCE
    )


def promote_episode(fabric: MemoryFabric, record: MemoryRecord) -> MemoryRecord | None:
    """Promote a reused, high-confidence episode to the semantic layer (idempotent)."""
    if not eligible_for_promotion(record):
        return None
    if fabric.semantic_exists_for(record.memory_id):
        return None
    semantic = MemoryRecord(
        scope=MemoryScope.SEMANTIC,
        task_id=record.task_id,
        summary=record.summary,
        salience=record.salience,
        confidence=record.confidence,
        source_refs=[record.memory_id],
    )
    fabric.write(semantic)
    return semantic


def publish_skill(
    fabric: MemoryFabric,
    *,
    summary: str,
    test_pass_rate: float,
    source_refs: list[str],
    task_id: str | None = None,
) -> MemoryRecord | None:
    """Publish a reusable procedure to the skill layer only if it passes its tests."""
    if test_pass_rate < SKILL_MIN_TEST_PASS_RATE:
        return None
    skill = MemoryRecord(
        scope=MemoryScope.SKILL,
        task_id=task_id,
        summary=summary,
        salience=0.8,
        confidence=test_pass_rate,
        source_refs=source_refs,
    )
    fabric.write(skill)
    return skill
