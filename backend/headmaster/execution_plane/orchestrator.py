"""Orchestrator — drives the task state machine through the core loop:

    plan -> execute -> critique -> (repair | publish -> assimilate)

Every state transition and every model/tool interaction is emitted as an
event; the event log is the single source of truth (replayable).
"""

from pathlib import Path

from pydantic import BaseModel

from headmaster.assurance_plane.critic_service import CriticService, requirements_for
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.schemas.artifact import Artifact, content_sha256
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness
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


class Orchestrator:
    def __init__(
        self,
        *,
        store: EventStore,
        agent_runtime: AgentRuntime,
        critic: CriticService,
        registry: dict[str, AgentHarness],
        max_revisions: int = 2,
        artifact_dir: Path | None = None,
    ) -> None:
        self._store = store
        self._agent_runtime = agent_runtime
        self._critic = critic
        self._registry = registry
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

    async def run_task(self, spec: TaskSpec, harness_id: str) -> OrchestratorResult:
        harness = self._registry.get(harness_id)
        if harness is None:
            raise KeyError(f"unknown agent harness: {harness_id}")
        task_id = spec.task_id
        state = TaskState.REGISTERED
        self._emit(task_id, EventType.TASK_REGISTERED, {"spec": spec.model_dump(mode="json")})

        state = self._transition(task_id, state, TaskState.CLASSIFIED)
        self._emit(task_id, EventType.TASK_CLASSIFIED, {"harness_id": harness_id})

        requirements = requirements_for(harness)
        self._emit(
            task_id,
            EventType.HARNESS_COMPILED,
            {"harness_id": harness_id, "version": harness.version},
        )

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
            )

            state = self._transition(task_id, state, TaskState.CRITIQUING)
            critique = self._critic.review(
                target_agent=harness_id,
                bundle=draft.bundle,
                requirements=requirements,
                task_id=task_id,
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
                self._emit(
                    task_id,
                    EventType.KNOWLEDGE_ASSIMILATED,
                    {
                        "candidate": {
                            "scope": "episodic",
                            "summary": f"{harness_id} deliverable approved for task {task_id}",
                            "source_refs": [artifact.artifact_id],
                        }
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
                )

            if attempt >= self._max_revisions:
                state = self._transition(task_id, state, TaskState.FAILED)
                self._emit(
                    task_id,
                    EventType.TASK_FAILED,
                    {"reason": "critic_rejected_max_revisions", "attempts": attempt + 1},
                )
                return OrchestratorResult(
                    task_id=task_id, final_state=state, critiques=critiques
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
