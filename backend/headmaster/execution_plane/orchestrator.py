"""Orchestrator — drives the task state machine through the core loop:

    supply knowledge -> plan -> execute -> critique -> (repair | publish -> assimilate)

Every state transition and every model/tool interaction is emitted as an
event; the event log is the single source of truth (replayable).

Knowledge circulation (Phase 2): the KnowledgeManager supplies the
imitation base before execution, the critic verifies referential integrity
against it, and approved/rejected results are capitalized/quarantined after.
Bootstrap rule: when the memory store has nothing to supply, the imitation
requirement is relaxed so the very first task can pass on benchmarks alone.
"""

from pathlib import Path

from pydantic import BaseModel

from headmaster.assurance_plane.critic_service import CriticService, requirements_for
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.memory.knowledge_manager import KnowledgeManager
from headmaster.schemas.artifact import Artifact, content_sha256
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness, IBFRequirements
from headmaster.schemas.memory_record import MemoryRecord
from headmaster.schemas.states import TaskState, validate_transition
from headmaster.schemas.task_spec import TaskSpec
from headmaster.storage.event_store import EventStore

SOURCE = "headmaster.orchestrator"


class OrchestratorResult(BaseModel):
    task_id: str
    final_state: TaskState
    artifact: Artifact | None = None
    critiques: list[CritiqueReport] = []
    artifact_path: str | None = None
    supplied_asset_ids: list[str] = []
    reused_asset_ids: list[str] = []


class Orchestrator:
    def __init__(
        self,
        *,
        store: EventStore,
        agent_runtime: AgentRuntime,
        critic: CriticService,
        registry: dict[str, AgentHarness],
        knowledge_manager: KnowledgeManager | None = None,
        max_revisions: int = 2,
        artifact_dir: Path | None = None,
    ) -> None:
        self._store = store
        self._agent_runtime = agent_runtime
        self._critic = critic
        self._registry = registry
        self._km = knowledge_manager
        self._max_revisions = max_revisions
        self._artifact_dir = artifact_dir

    def _emit(self, task_id: str, event_type: EventType, data: dict[str, object]) -> None:
        self._store.append(
            Event(source=SOURCE, type=event_type, subject=task_id, data=dict(data))
        )

    def _transition(self, task_id: str, current: TaskState, target: TaskState) -> TaskState:
        validate_transition(current, target)
        self._emit(
            task_id,
            EventType.STATE_CHANGED,
            {"from": current.value, "to": target.value},
        )
        return target

    def _supply_knowledge(
        self, spec: TaskSpec, requirements: IBFRequirements
    ) -> tuple[list[MemoryRecord], IBFRequirements]:
        supplied = self._km.supply(spec) if self._km else []
        effective = requirements
        bootstrap = False
        if requirements.must_reference_internal_assets and not supplied:
            effective = requirements.model_copy(
                update={"must_reference_internal_assets": False}
            )
            bootstrap = True
        self._emit(
            spec.task_id,
            EventType.KNOWLEDGE_SUPPLIED,
            {
                "asset_ids": [record.memory_id for record in supplied],
                "count": len(supplied),
                "bootstrap": bootstrap,
            },
        )
        return supplied, effective

    async def run_task(self, spec: TaskSpec, harness_id: str) -> OrchestratorResult:
        harness = self._registry.get(harness_id)
        if harness is None:
            raise KeyError(f"unknown agent harness: {harness_id}")
        task_id = spec.task_id
        state = TaskState.REGISTERED
        self._emit(task_id, EventType.TASK_REGISTERED, {"spec": spec.model_dump(mode="json")})

        state = self._transition(task_id, state, TaskState.CLASSIFIED)
        self._emit(task_id, EventType.TASK_CLASSIFIED, {"harness_id": harness_id})

        self._emit(
            task_id,
            EventType.HARNESS_COMPILED,
            {"harness_id": harness_id, "version": harness.version},
        )
        supplied, requirements = self._supply_knowledge(spec, requirements_for(harness))
        supplied_ids = {record.memory_id for record in supplied}

        state = self._transition(task_id, state, TaskState.PLANNED)
        self._emit(task_id, EventType.PLAN_CREATED, {"steps": [harness_id], "revision": 0})

        critiques: list[CritiqueReport] = []
        revision_notes: list[str] = []
        attempt = 0
        while True:
            state = self._transition(task_id, state, TaskState.EXECUTING)
            self._emit(
                task_id,
                EventType.AGENT_DISPATCHED,
                {"agent": harness_id, "attempt": attempt},
            )
            draft = await self._agent_runtime.run(
                harness=harness,
                task=spec,
                requirements=requirements,
                revision_notes=revision_notes,
                emit=self._store.append,
                supplied_assets=supplied,
            )

            state = self._transition(task_id, state, TaskState.CRITIQUING)
            critique = self._critic.review(
                target_agent=harness_id,
                bundle=draft.bundle,
                requirements=requirements,
                task_id=task_id,
                supplied_asset_ids=supplied_ids if supplied_ids else None,
            )
            critiques.append(critique)
            self._emit(task_id, EventType.CRITIQUE_ISSUED, critique.model_dump(mode="json"))

            if critique.accepted:
                state = self._transition(task_id, state, TaskState.VALIDATED)
                state = self._transition(task_id, state, TaskState.PUBLISHING)
                artifact = Artifact(
                    task_id=task_id,
                    produced_by=harness_id,
                    format=harness.output_contract.format,
                    content=draft.content,
                    content_hash=content_sha256(draft.content),
                    evidence_bundle_id=draft.bundle.bundle_id,
                    critique_id=critique.critique_id,
                )
                artifact_path: str | None = None
                if self._artifact_dir is not None:
                    self._artifact_dir.mkdir(parents=True, exist_ok=True)
                    path = self._artifact_dir / f"{task_id}.md"
                    path.write_text(artifact.content, encoding="utf-8")
                    artifact_path = str(path)
                self._emit(
                    task_id,
                    EventType.ARTIFACT_PUBLISHED,
                    {
                        "artifact_id": artifact.artifact_id,
                        "content_hash": artifact.content_hash,
                        "path": artifact_path,
                    },
                )
                state = self._transition(task_id, state, TaskState.ASSIMILATING)
                proof = draft.bundle.ibf_proof
                reused = [
                    asset
                    for asset in (proof.imitated_assets if proof else [])
                    if asset in supplied_ids
                ]
                promoted: list[MemoryRecord] = []
                records: list[MemoryRecord] = []
                if self._km is not None:
                    promoted = self._km.record_reuse(reused) if reused else []
                    records = self._km.maintain(
                        task=spec, harness_id=harness_id, artifact=artifact, critique=critique
                    )
                self._emit(
                    task_id,
                    EventType.KNOWLEDGE_ASSIMILATED,
                    {
                        "records": [record.memory_id for record in records],
                        "reused_assets": reused,
                        "promoted": [record.memory_id for record in promoted],
                        "quarantined": False,
                    },
                )
                state = self._transition(task_id, state, TaskState.COMPLETED)
                self._emit(task_id, EventType.TASK_COMPLETED, {"attempts": attempt + 1})
                return OrchestratorResult(
                    task_id=task_id,
                    final_state=state,
                    artifact=artifact,
                    critiques=critiques,
                    artifact_path=artifact_path,
                    supplied_asset_ids=sorted(supplied_ids),
                    reused_asset_ids=reused,
                )

            if attempt >= self._max_revisions:
                records = []
                if self._km is not None:
                    records = self._km.maintain(
                        task=spec, harness_id=harness_id, artifact=None, critique=critique
                    )
                    self._emit(
                        task_id,
                        EventType.KNOWLEDGE_ASSIMILATED,
                        {
                            "records": [record.memory_id for record in records],
                            "reused_assets": [],
                            "promoted": [],
                            "quarantined": True,
                        },
                    )
                state = self._transition(task_id, state, TaskState.FAILED)
                self._emit(
                    task_id,
                    EventType.TASK_FAILED,
                    {"reason": "critic_rejected_max_revisions", "attempts": attempt + 1},
                )
                return OrchestratorResult(
                    task_id=task_id,
                    final_state=state,
                    critiques=critiques,
                    supplied_asset_ids=sorted(supplied_ids),
                )

            attempt += 1
            revision_notes = list(critique.mandatory_revisions)
            state = self._transition(task_id, state, TaskState.REPLANNING)
            self._emit(
                task_id,
                EventType.REPLAN_TRIGGERED,
                {"revisions": revision_notes, "attempt": attempt},
            )
            state = self._transition(task_id, state, TaskState.PLANNED)
            self._emit(
                task_id, EventType.PLAN_CREATED, {"steps": [harness_id], "revision": attempt}
            )
