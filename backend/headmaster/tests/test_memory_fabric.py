"""Phase 2: memory fabric — quarantine isolation and gated consolidation."""

from headmaster.execution_plane.memory import (
    MemoryFabric,
    eligible_for_promotion,
    promote_episode,
    publish_skill,
)
from headmaster.schemas import MemoryRecord, MemoryScope


def _episode(*, quarantine: bool = False, confidence: float = 0.9) -> MemoryRecord:
    return MemoryRecord(
        scope=MemoryScope.EPISODIC,
        summary="proven sitemap skeleton for B2B SaaS",
        salience=0.8,
        confidence=confidence,
        quarantine=quarantine,
    )


def test_write_get_roundtrip() -> None:
    fabric = MemoryFabric()
    record = _episode()
    fabric.write(record)
    loaded = fabric.get(record.memory_id)
    assert loaded is not None
    assert loaded.model_dump() == record.model_dump()


def test_quarantine_excluded_from_default_search() -> None:
    fabric = MemoryFabric()
    good, bad = _episode(), _episode(quarantine=True)
    fabric.write(good)
    fabric.write(bad)
    default_results = fabric.search()
    assert [r.memory_id for r in default_results] == [good.memory_id]
    all_results = fabric.search(include_quarantined=True)
    assert {r.memory_id for r in all_results} == {good.memory_id, bad.memory_id}


def test_search_scope_filter_and_keyword() -> None:
    fabric = MemoryFabric()
    episode = _episode()
    skill = MemoryRecord(scope=MemoryScope.SKILL, summary="citation validation procedure")
    fabric.write(episode)
    fabric.write(skill)
    assert {r.memory_id for r in fabric.search(scopes=[MemoryScope.SKILL])} == {skill.memory_id}
    assert [r.memory_id for r in fabric.search(keyword="sitemap")] == [episode.memory_id]


def test_promotion_gate_requires_reuse_and_confidence() -> None:
    fabric = MemoryFabric()
    record = _episode()
    fabric.write(record)
    assert eligible_for_promotion(record) is False  # reuse_count 0

    once = fabric.increment_reuse(record.memory_id)
    assert once is not None and once.reuse_count == 1
    assert eligible_for_promotion(once) is False

    twice = fabric.increment_reuse(record.memory_id)
    assert twice is not None and twice.reuse_count == 2
    assert eligible_for_promotion(twice) is True

    low_confidence = _episode(confidence=0.5)
    low_confidence = low_confidence.model_copy(update={"reuse_count": 5})
    assert eligible_for_promotion(low_confidence) is False

    quarantined = _episode(quarantine=True).model_copy(update={"reuse_count": 5})
    assert eligible_for_promotion(quarantined) is False


def test_promote_episode_is_idempotent() -> None:
    fabric = MemoryFabric()
    record = _episode()
    fabric.write(record)
    fabric.increment_reuse(record.memory_id)
    reinforced = fabric.increment_reuse(record.memory_id)
    assert reinforced is not None

    semantic = promote_episode(fabric, reinforced)
    assert semantic is not None
    assert semantic.scope is MemoryScope.SEMANTIC
    assert semantic.source_refs == [record.memory_id]
    assert promote_episode(fabric, reinforced) is None  # already promoted


def test_skill_publish_gate() -> None:
    fabric = MemoryFabric()
    rejected = publish_skill(
        fabric, summary="flaky procedure", test_pass_rate=0.8, source_refs=["art_x"]
    )
    assert rejected is None
    published = publish_skill(
        fabric, summary="solid procedure", test_pass_rate=0.95, source_refs=["art_x"]
    )
    assert published is not None
    assert fabric.search(scopes=[MemoryScope.SKILL])[0].memory_id == published.memory_id
