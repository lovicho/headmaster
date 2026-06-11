"""Phase 3 gates: high-risk tasks cannot publish without approval;
budget soft limit downgrades the tier, hard limit halts for approval;
the audit trail records who decided / based on what / who approved."""

import asyncio

from headmaster.assurance_plane.approval_gateway import (
    ApprovalGateway,
    CallbackApprovalGateway,
)
from headmaster.assurance_plane.audit import build_audit_trail
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.budget_ledger import ModelPrice
from headmaster.control_plane.harness_registry import load_all
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import (
    AgentHarness,
    ApprovalDecision,
    Budget,
    Constraints,
    CostTier,
    EventType,
    RiskProfile,
    TaskSpec,
    TaskState,
)
from headmaster.storage.event_store import EventStore
from headmaster.tests.test_orchestrator import NO_PROOF_RESPONSE, VALID_RESPONSE

FAKE_PRICING = {"fake": {"default": ModelPrice(input_per_mtok=1.0, output_per_mtok=1.0)}}


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def _orchestrator(
    store: EventStore,
    *,
    responses: list[str] | None = None,
    approval: ApprovalGateway | None = None,
    max_revisions: int = 2,
) -> Orchestrator:
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    return Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        approval_gateway=approval,
        max_revisions=max_revisions,
    )


def _high_risk_spec() -> TaskSpec:
    return TaskSpec(
        title="고위험 작업",
        intent="고위험 작업",
        risk_profile=RiskProfile(needs_human_approval=True),
    )


def test_high_risk_without_gateway_is_never_published() -> None:
    """Gate: needs_human_approval + no gateway -> deny by default, no artifact."""
    store = EventStore()
    result = asyncio.run(
        _orchestrator(store, responses=[VALID_RESPONSE]).run_task(_high_risk_spec(), "content")
    )
    assert result.final_state is TaskState.FAILED
    assert result.failure_reason == "approval_denied"
    assert result.artifact is None
    types = [e.type for e in store.for_task(result.task_id)]
    assert EventType.APPROVAL_REQUESTED in types
    assert EventType.APPROVAL_DENIED in types
    assert EventType.ARTIFACT_PUBLISHED not in types


def test_high_risk_published_only_after_grant() -> None:
    store = EventStore()
    gateway = CallbackApprovalGateway(
        lambda ticket: ApprovalDecision(granted=True, approver="boss")
    )
    result = asyncio.run(
        _orchestrator(store, responses=[VALID_RESPONSE], approval=gateway).run_task(
            _high_risk_spec(), "content"
        )
    )
    assert result.final_state is TaskState.COMPLETED
    assert result.artifact is not None
    assert gateway.tickets[0].kind == "publish"
    granted = next(
        e for e in store.for_task(result.task_id) if e.type is EventType.APPROVAL_GRANTED
    )
    assert granted.data["approver"] == "boss"


def test_audit_trail_records_decisions() -> None:
    """Gate: who decided / based on what / who approved."""
    store = EventStore()
    gateway = CallbackApprovalGateway(
        lambda ticket: ApprovalDecision(granted=True, approver="boss", note="reviewed")
    )
    result = asyncio.run(
        _orchestrator(store, responses=[VALID_RESPONSE], approval=gateway).run_task(
            _high_risk_spec(), "content"
        )
    )
    trail = build_audit_trail(store.for_task(result.task_id))
    critic_entries = [entry for entry in trail if entry.actor == "critic"]
    assert critic_entries and "imitation_check" in critic_entries[0].basis  # based on what
    approver_entries = [entry for entry in trail if entry.actor == "boss"]
    assert approver_entries and approver_entries[0].action == "approval granted"


def _budget_spec(max_tokens: int) -> TaskSpec:
    return TaskSpec(
        title="예산 작업",
        intent="예산 작업",
        constraints=Constraints(budget=Budget(max_tokens=max_tokens)),
    )


def _run_budget(
    store: EventStore,
    *,
    max_tokens: int,
    responses: list[str],
    approval: ApprovalGateway | None,
) -> OrchestratorResult:
    gateway = ModelGateway(
        load_routing(), {"fake": FakeAdapter(responses)}, provider_override="fake"
    )
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        approval_gateway=approval,
        pricing=FAKE_PRICING,  # fake usage: 150 tokens per call
        max_revisions=2,
    )
    return asyncio.run(orchestrator.run_task(_budget_spec(max_tokens), "content"))


def test_within_budget_emits_no_budget_events() -> None:
    # fake usage: 150 tokens/call; 2 calls = 300 < soft 320 < hard 400
    store = EventStore()
    result = _run_budget(
        store,
        max_tokens=400,
        responses=[NO_PROOF_RESPONSE, VALID_RESPONSE],
        approval=None,
    )
    assert result.final_state is TaskState.COMPLETED
    assert not [
        e for e in store.for_task(result.task_id) if e.type is EventType.BUDGET_EXCEEDED
    ]


def test_soft_limit_downgrades_tier() -> None:
    # max 370 -> soft 296: attempt 2 starts with 300 spent -> downgrade; hard 370 untouched
    store = EventStore()
    result = _run_budget(
        store,
        max_tokens=370,
        responses=[NO_PROOF_RESPONSE, NO_PROOF_RESPONSE, VALID_RESPONSE],
        approval=None,
    )
    assert result.final_state is TaskState.COMPLETED
    events = store.for_task(result.task_id)
    soft_events = [
        e
        for e in events
        if e.type is EventType.BUDGET_EXCEEDED and e.data["severity"] == "soft"
    ]
    assert soft_events, "soft limit must trigger a tier downgrade event"
    assert soft_events[0].data["action"] == "downgrade_tier"
    assert soft_events[0].data["from"] == CostTier.STANDARD.value
    assert soft_events[0].data["to"] == CostTier.MINI.value


def test_hard_limit_halts_and_requires_approval() -> None:
    deny = CallbackApprovalGateway(
        lambda ticket: ApprovalDecision(granted=False, approver="boss")
    )
    store = EventStore()
    result = _run_budget(
        store,
        max_tokens=200,  # hard at 200: attempt 1 spent 150 ok... attempt 2 spent 300 -> halt
        responses=[NO_PROOF_RESPONSE, NO_PROOF_RESPONSE, VALID_RESPONSE],
        approval=deny,
    )
    assert result.final_state is TaskState.FAILED
    assert result.failure_reason == "budget_hard_limit_denied"
    assert deny.tickets and deny.tickets[0].kind == "budget_overrun"
    events = store.for_task(result.task_id)
    hard_events = [
        e
        for e in events
        if e.type is EventType.BUDGET_EXCEEDED and e.data["severity"] == "hard"
    ]
    assert hard_events


def test_hard_limit_continues_after_grant() -> None:
    grant = CallbackApprovalGateway(
        lambda ticket: ApprovalDecision(granted=True, approver="boss")
    )
    store = EventStore()
    result = _run_budget(
        store,
        max_tokens=200,  # attempt 2 starts with 300 spent >= 200 -> approval, then continue
        responses=[NO_PROOF_RESPONSE, NO_PROOF_RESPONSE, VALID_RESPONSE],
        approval=grant,
    )
    assert result.final_state is TaskState.COMPLETED
    assert any(ticket.kind == "budget_overrun" for ticket in grant.tickets)
