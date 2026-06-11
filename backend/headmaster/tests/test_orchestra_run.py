"""Phase 3: multi-agent orchestra fan-out with phase gates (offline)."""

import asyncio

from headmaster.assurance_plane.approval_gateway import CallbackApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.memory import KnowledgeManager, MemoryFabric
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import (
    AgentHarness,
    ApprovalDecision,
    EventType,
    OrchestraHarness,
    TaskState,
)
from headmaster.storage.event_store import EventStore


def _load() -> tuple[dict[str, AgentHarness], OrchestraHarness]:
    all_harnesses = load_all()
    registry = {
        harness_id: harness
        for harness_id, harness in all_harnesses.items()
        if isinstance(harness, AgentHarness)
    }
    orchestra = all_harnesses["b2b_website_v8"]
    assert isinstance(orchestra, OrchestraHarness)
    return registry, orchestra


def _run(
    store: EventStore,
    *,
    grant: bool,
    fabric: MemoryFabric | None = None,
) -> tuple[OrchestratorResult, CallbackApprovalGateway, OrchestraHarness]:
    registry, orchestra = _load()
    gateway = CallbackApprovalGateway(
        lambda ticket: ApprovalDecision(granted=grant, approver="boss")
    )
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(
            ModelGateway(load_routing(), {"fake": FakeAdapter()}, provider_override="fake")
        ),
        critic=CriticService(),
        registry=registry,
        knowledge_manager=KnowledgeManager(fabric) if fabric is not None else None,
        approval_gateway=gateway,
    )
    spec = compile_task("B2B 웹사이트 구축")
    result = asyncio.run(orchestrator.run_orchestra(spec, orchestra))
    return result, gateway, orchestra


def test_orchestra_completes_all_phases_with_fanout() -> None:
    store = EventStore()
    result, gateway, orchestra = _run(store, grant=True)
    assert result.final_state is TaskState.COMPLETED
    assert result.artifact is not None

    total_agents = sum(len(phase.agents) for phase in orchestra.phases)
    approved = [c for c in result.critiques if c.accepted]
    assert len(approved) == total_agents

    events = store.for_task(result.task_id)
    # fan-out: phase_0 has 3 agents -> 3 dispatches inside one EXECUTING window
    phase0_dispatches = [
        e
        for e in events
        if e.type is EventType.AGENT_DISPATCHED and e.data.get("phase") == "phase_0"
    ]
    assert len(phase0_dispatches) == 3
    # the human gate (gate_0) was actually requested and granted
    assert any(ticket.kind == "phase_gate" for ticket in gateway.tickets)
    assert any(e.type is EventType.APPROVAL_GRANTED for e in events)
    # combined artifact contains a section per agent
    for phase in orchestra.phases:
        for agent_id in phase.agents:
            assert f"[{phase.phase_id}/{agent_id}]" in result.artifact.content


def test_orchestra_human_gate_denial_blocks_run() -> None:
    store = EventStore()
    result, gateway, _ = _run(store, grant=False)
    assert result.final_state is TaskState.FAILED
    assert result.failure_reason == "approval_denied"
    assert result.artifact is None
    events = store.for_task(result.task_id)
    assert any(e.type is EventType.APPROVAL_DENIED for e in events)
    assert not any(e.type is EventType.ARTIFACT_PUBLISHED for e in events)


def test_orchestra_assimilates_combined_artifact() -> None:
    store, fabric = EventStore(), MemoryFabric()
    result, _, orchestra = _run(store, grant=True, fabric=fabric)
    assert result.final_state is TaskState.COMPLETED
    episodes = fabric.search()
    assert any(orchestra.harness_id in record.summary for record in episodes)
