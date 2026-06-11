"""Phase 2 gates: knowledge circulation end-to-end (offline).

- the 2nd task actually reuses the 1st task's asset as imitation base
  (verified via the event trace and reuse counters)
- the 3rd reuse crosses the consolidation gate -> semantic promotion
- failed tasks are quarantined and excluded from the next supply
"""

import asyncio

from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.memory import KnowledgeManager, MemoryFabric
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import AgentHarness, EventType, MemoryScope, TaskState
from headmaster.storage.event_store import EventStore
from headmaster.tests.test_orchestrator import NO_PROOF_RESPONSE


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def _run_task(
    store: EventStore,
    fabric: MemoryFabric,
    text: str,
    *,
    responses: list[str] | None = None,
    max_revisions: int = 2,
) -> OrchestratorResult:
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        knowledge_manager=KnowledgeManager(fabric),
        max_revisions=max_revisions,
    )
    return asyncio.run(orchestrator.run_task(compile_task(text), "content"))


def test_second_task_reuses_first_tasks_asset() -> None:
    store, fabric = EventStore(), MemoryFabric()

    first = _run_task(store, fabric, "첫 번째 작업")
    assert first.final_state is TaskState.COMPLETED
    assert first.supplied_asset_ids == []  # cold start (bootstrap)
    first_records = {
        record.memory_id for record in fabric.search(scopes=[MemoryScope.EPISODIC])
    }
    assert len(first_records) == 1

    second = _run_task(store, fabric, "두 번째 작업")
    assert second.final_state is TaskState.COMPLETED
    assert set(second.supplied_asset_ids) >= first_records
    assert set(second.reused_asset_ids) & first_records  # actual reuse happened

    # trace-level verification (gate: reuse visible in the event log)
    events = store.for_task(second.task_id)
    supplied_event = next(e for e in events if e.type is EventType.KNOWLEDGE_SUPPLIED)
    assert supplied_event.data["bootstrap"] is False
    assert set(supplied_event.data["asset_ids"]) >= first_records
    assimilated = next(e for e in events if e.type is EventType.KNOWLEDGE_ASSIMILATED)
    assert set(assimilated.data["reused_assets"]) & first_records

    reused_id = next(iter(first_records))
    reused_record = fabric.get(reused_id)
    assert reused_record is not None
    assert reused_record.reuse_count == 1


def test_third_reuse_promotes_to_semantic() -> None:
    store, fabric = EventStore(), MemoryFabric()
    _run_task(store, fabric, "작업 1")
    _run_task(store, fabric, "작업 2")
    third = _run_task(store, fabric, "작업 3")
    assert third.final_state is TaskState.COMPLETED

    semantic = fabric.search(scopes=[MemoryScope.SEMANTIC])
    assert semantic, "a twice-reused episode must be promoted to the semantic layer"
    promoted_event = next(
        e
        for e in store.for_task(third.task_id)
        if e.type is EventType.KNOWLEDGE_ASSIMILATED
    )
    assert promoted_event.data["promoted"] == [semantic[0].memory_id]


def test_failed_task_is_quarantined_and_excluded_from_supply() -> None:
    store, fabric = EventStore(), MemoryFabric()
    failed = _run_task(
        store,
        fabric,
        "실패 작업",
        responses=[NO_PROOF_RESPONSE, NO_PROOF_RESPONSE],
        max_revisions=1,
    )
    assert failed.final_state is TaskState.FAILED

    assert fabric.search() == []  # excluded from default retrieval
    quarantined = fabric.search(include_quarantined=True)
    assert len(quarantined) == 1
    assert quarantined[0].quarantine is True

    events = store.for_task(failed.task_id)
    assimilated = next(e for e in events if e.type is EventType.KNOWLEDGE_ASSIMILATED)
    assert assimilated.data["quarantined"] is True

    # next task must not receive the quarantined record as imitation base
    follow_up = _run_task(store, fabric, "후속 작업")
    assert follow_up.supplied_asset_ids == []
    assert follow_up.final_state is TaskState.COMPLETED
