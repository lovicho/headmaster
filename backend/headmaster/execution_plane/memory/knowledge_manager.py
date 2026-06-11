"""KnowledgeManager — operator of the asset economy (v8 + 1st report).

Pre-work: supplies the [Mandatory_Imitation_Base] from non-quarantined
memory. Post-work: capitalizes approved deliverables into episodic and
evidence records, quarantines rejected ones, reinforces reused assets and
triggers gated promotion.
"""

from collections.abc import Iterable

from headmaster.execution_plane.memory.consolidation import (
    eligible_for_promotion,
    promote_episode,
)
from headmaster.execution_plane.memory.fabric import MemoryFabric
from headmaster.schemas.artifact import Artifact
from headmaster.schemas.common import MemoryScope
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.memory_record import DecayPolicy, MemoryRecord
from headmaster.schemas.task_spec import TaskSpec

SUPPLY_SCOPES = [MemoryScope.EPISODIC, MemoryScope.SEMANTIC, MemoryScope.SKILL]


class KnowledgeManager:
    def __init__(self, fabric: MemoryFabric, supply_limit: int = 5) -> None:
        self._fabric = fabric
        self._supply_limit = supply_limit

    def supply(self, task: TaskSpec) -> list[MemoryRecord]:
        """Pre-work supply of imitation-base assets (quarantined records excluded)."""
        return self._fabric.search(scopes=SUPPLY_SCOPES, limit=self._supply_limit)

    def maintain(
        self,
        *,
        task: TaskSpec,
        harness_id: str,
        artifact: Artifact | None,
        critique: CritiqueReport,
    ) -> list[MemoryRecord]:
        """Post-work capitalization: archive success, quarantine failure."""
        if critique.accepted and artifact is not None:
            episode = MemoryRecord(
                scope=MemoryScope.EPISODIC,
                task_id=task.task_id,
                summary=f"[{harness_id}] approved deliverable for: {task.title}",
                salience=0.8,
                confidence=0.9,
                source_refs=[artifact.artifact_id],
            )
            evidence = MemoryRecord(
                scope=MemoryScope.EVIDENCE,
                task_id=task.task_id,
                summary=f"[{harness_id}] artifact {artifact.artifact_id}"
                f" sha256={artifact.content_hash}",
                salience=0.5,
                confidence=1.0,
                decay_policy=DecayPolicy.IMMUTABLE,
                source_refs=[artifact.artifact_id, critique.critique_id],
            )
            self._fabric.write(episode)
            self._fabric.write(evidence)
            return [episode, evidence]

        reason = (
            critique.mandatory_revisions[0]
            if critique.mandatory_revisions
            else "rejected by critic"
        )
        quarantined = MemoryRecord(
            scope=MemoryScope.EPISODIC,
            task_id=task.task_id,
            summary=f"[{harness_id}] REJECTED for: {task.title} — {reason}",
            salience=0.6,
            confidence=0.2,
            source_refs=[critique.critique_id],
            quarantine=True,
        )
        self._fabric.write(quarantined)
        return [quarantined]

    def record_reuse(self, asset_ids: Iterable[str]) -> list[MemoryRecord]:
        """Reinforce reused assets; promote episodes that pass the consolidation gate."""
        promoted: list[MemoryRecord] = []
        for asset_id in asset_ids:
            record = self._fabric.increment_reuse(asset_id)
            if record is not None and eligible_for_promotion(record):
                semantic = promote_episode(self._fabric, record)
                if semantic is not None:
                    promoted.append(semantic)
        return promoted
