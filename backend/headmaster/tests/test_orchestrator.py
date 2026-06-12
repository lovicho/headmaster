"""Phase 1 gates 1-1 / 1-3 / 1-5: end-to-end loop, replay determinism,
and full event coverage of model interactions — all offline."""

import asyncio
import json
from pathlib import Path

from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import AgentHarness, CritiqueStatus, EventType, TaskState
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_final_state, replay_states

VALID_RESPONSE = json.dumps(
    {
        "ibf_proof": {
            "imitated_assets": [],
            "benchmarked_references": ["https://example.com/ref"],
            "fusion_method": "Fused imitation base with task facts.",
        },
        "content": "# 산출물\n\n테스트 결과물입니다.",
    }
)
NO_PROOF_RESPONSE = json.dumps({"content": "zero-shot draft without provenance"})


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def _orchestrator(
    store: EventStore,
    responses: list[str] | None,
    *,
    max_revisions: int = 2,
    artifact_dir: Path | None = None,
) -> Orchestrator:
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    return Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        max_revisions=max_revisions,
        artifact_dir=artifact_dir,
    )


def _run(
    store: EventStore,
    responses: list[str] | None,
    *,
    max_revisions: int = 2,
    artifact_dir: Path | None = None,
) -> OrchestratorResult:
    orchestrator = _orchestrator(
        store, responses, max_revisions=max_revisions, artifact_dir=artifact_dir
    )
    spec = compile_task("테스트용 데모 작업")
    return asyncio.run(orchestrator.run_task(spec, "content"))


def test_e2e_success_path(tmp_path: Path) -> None:
    store = EventStore()
    result = _run(store, [VALID_RESPONSE], artifact_dir=tmp_path)
    assert result.final_state is TaskState.COMPLETED
    assert result.artifact is not None
    assert result.artifact.content_hash
    assert result.artifact_path is not None
    assert Path(result.artifact_path).read_text(encoding="utf-8").startswith("# 산출물")
    assert len(result.critiques) == 1
    assert result.critiques[0].status is CritiqueStatus.APPROVED


def test_every_model_call_is_logged() -> None:
    store = EventStore()
    result = _run(store, [VALID_RESPONSE])
    types = [event.type for event in store.for_task(result.task_id)]
    for expected in (
        EventType.TASK_REGISTERED,
        EventType.HARNESS_COMPILED,
        EventType.MODEL_CALLED,
        EventType.MODEL_RESPONDED,
        EventType.ARTIFACT_PRODUCED,
        EventType.CRITIQUE_ISSUED,
        EventType.ARTIFACT_PUBLISHED,
        EventType.KNOWLEDGE_ASSIMILATED,
        EventType.TASK_COMPLETED,
    ):
        assert expected in types, expected
    assert types.count(EventType.MODEL_CALLED) == types.count(EventType.MODEL_RESPONDED) == 1


def test_rejection_then_repair_loop() -> None:
    store = EventStore()
    result = _run(store, [NO_PROOF_RESPONSE, VALID_RESPONSE])
    assert result.final_state is TaskState.COMPLETED
    assert len(result.critiques) == 2
    assert result.critiques[0].status is CritiqueStatus.REJECTED
    assert result.critiques[0].zero_shot_detected is True
    assert result.critiques[1].status is CritiqueStatus.APPROVED
    types = [event.type for event in store.for_task(result.task_id)]
    assert EventType.REPLAN_TRIGGERED in types


def test_max_revisions_exhausted_fails() -> None:
    store = EventStore()
    result = _run(store, [NO_PROOF_RESPONSE, NO_PROOF_RESPONSE], max_revisions=1)
    assert result.final_state is TaskState.FAILED
    assert result.artifact is None
    types = [event.type for event in store.for_task(result.task_id)]
    assert EventType.TASK_FAILED in types


def test_replay_determinism(tmp_path: Path) -> None:
    """Gate 1-3: the state sequence folded from the persisted log is identical
    across replays and matches the live final state."""
    store_path = tmp_path / "events.sqlite3"
    store = EventStore(store_path)
    result = _run(store, [NO_PROOF_RESPONSE, VALID_RESPONSE])
    store.close()

    reopened = EventStore(store_path)
    events = reopened.for_task(result.task_id)
    first = replay_states(events)
    second = replay_states(reopened.for_task(result.task_id))
    reopened.close()

    assert first == second
    assert first[-1] is result.final_state
    assert replay_final_state(events) is TaskState.COMPLETED
    # every transition in the replayed sequence was validated by replay_states
    assert first[0] is TaskState.REGISTERED
    assert TaskState.REPLANNING in first
