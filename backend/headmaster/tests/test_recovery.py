"""Phase 4d: fault recovery — model failures retry through RECOVERING."""

import asyncio

from headmaster.assurance_plane.approval_gateway import CallbackApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.models.fake_adapter import FakeScript
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import (
    AgentHarness,
    ApprovalDecision,
    EventType,
    OrchestraHarness,
    TaskState,
)
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_states
from headmaster.tests.test_orchestrator import VALID_RESPONSE


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def _orchestrator(
    store: EventStore, responses: list[FakeScript], *, max_recoveries: int = 2
) -> Orchestrator:
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    return Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        max_recoveries=max_recoveries,
    )


def test_run_task_recovers_from_model_error() -> None:
    store = EventStore()
    orchestrator = _orchestrator(store, [RuntimeError("boom"), VALID_RESPONSE])
    result = asyncio.run(orchestrator.run_task(compile_task("복구 테스트"), "content"))
    assert result.final_state is TaskState.COMPLETED

    events = store.for_task(result.task_id)
    recovery = [e for e in events if e.type is EventType.RECOVERY_STARTED]
    assert recovery and "boom" in recovery[0].data["error"]
    assert TaskState.RECOVERING in replay_states(events)


def test_run_task_fails_after_recovery_budget_exhausted() -> None:
    store = EventStore()
    orchestrator = _orchestrator(
        store,
        [RuntimeError("a"), RuntimeError("b"), RuntimeError("c")],
        max_recoveries=2,
    )
    result = asyncio.run(orchestrator.run_task(compile_task("복구 소진"), "content"))
    assert result.final_state is TaskState.FAILED
    assert result.failure_reason == "model_error"
    types = [e.type for e in store.for_task(result.task_id)]
    assert types.count(EventType.RECOVERY_STARTED) == 2
    assert EventType.TASK_FAILED in types


def _run_orchestra(
    store: EventStore, responses: list[FakeScript]
) -> OrchestratorResult:
    all_harnesses = load_all()
    orchestra = all_harnesses["b2b_website_v8"]
    assert isinstance(orchestra, OrchestraHarness)
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        approval_gateway=CallbackApprovalGateway(
            lambda ticket: ApprovalDecision(granted=True, approver="boss")
        ),
    )
    return asyncio.run(orchestrator.run_orchestra(compile_task("오케스트라 복구"), orchestra))


def test_orchestra_retries_only_failed_agent() -> None:
    # phase_0 runs [consultant, knowledge_manager, researcher] sorted; the first
    # fake script item raises for consultant, the retry then uses defaults.
    store = EventStore()
    result = _run_orchestra(store, [RuntimeError("flaky model")])
    assert result.final_state is TaskState.COMPLETED

    events = store.for_task(result.task_id)
    recovery = [e for e in events if e.type is EventType.RECOVERY_STARTED]
    assert len(recovery) == 1
    assert recovery[0].data["agent"] == "consultant"
