"""Tests for the resume and recovery boundary of the orchestrator."""

import asyncio
import json
from pathlib import Path

from headmaster.assurance_plane.approval_gateway import ApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.models.gateway import ModelGatewayError
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas import AgentHarness, ApprovalDecision, ApprovalTicket, TaskState
from headmaster.storage.event_store import EventStore

VALID_RESPONSE = json.dumps(
    {
        "ibf_proof": {
            "imitated_assets": [],
            "benchmarked_references": [],
            "fusion_method": "Test",
        },
        "content": "resumed output",
    }
)


class MockApprovalGateway(ApprovalGateway):
    """An approval gateway that pre-determines decisions."""

    def __init__(self, decisions: list[bool]):
        self.decisions = decisions
        self.tickets: list[ApprovalTicket] = []

    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision:
        self.tickets.append(ticket)
        granted = self.decisions.pop(0) if self.decisions else False
        return ApprovalDecision(
            granted=granted, approver="mock_user", note="test decision"
        )


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def test_resume_on_model_error_granted(tmp_path: Path) -> None:
    """If ModelGatewayError hits max_recoveries, it waits for human approval.
    If granted, it resumes execution."""
    store = EventStore()
    responses = [
        ModelGatewayError("Simulated failure 1"),
        ModelGatewayError("Simulated failure 2"),
        ModelGatewayError("Simulated failure 3"),
        VALID_RESPONSE,
    ]
    adapter = FakeAdapter(responses)
    gateway = ModelGateway(
        load_routing(), {"fake": adapter}, provider_override="fake"
    )
    
    approval = MockApprovalGateway(decisions=[True])

    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        approval_gateway=approval,
        max_revisions=2,
        max_recoveries=2,  # Should fail on 1st, 2nd, then ask approval on 3rd
        artifact_dir=tmp_path,
    )
    spec = compile_task("테스트용 데모 작업")
    
    result = asyncio.run(orchestrator.run_task(spec, "content"))
    
    # 3 failures -> max_recoveries=2 -> exceeded on 3rd attempt
    # Since granted=True, it resumes. On the 4th call, it succeeds.
    assert len(approval.tickets) == 1
    assert approval.tickets[0].kind == "recovery_limit_exceeded"
    
    assert result.final_state is TaskState.COMPLETED
    assert result.artifact is not None


def test_resume_on_model_error_denied(tmp_path: Path) -> None:
    """If human approval is denied, task fails."""
    store = EventStore()
    responses = [
        ModelGatewayError("Simulated failure 1"),
        ModelGatewayError("Simulated failure 2"),
        ModelGatewayError("Simulated failure 3"),
        VALID_RESPONSE,
    ]
    adapter = FakeAdapter(responses)
    gateway = ModelGateway(
        load_routing(), {"fake": adapter}, provider_override="fake"
    )
    
    approval = MockApprovalGateway(decisions=[False])

    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        approval_gateway=approval,
        max_revisions=2,
        max_recoveries=2,
        artifact_dir=tmp_path,
    )
    spec = compile_task("테스트용 데모 작업")
    
    result = asyncio.run(orchestrator.run_task(spec, "content"))
    
    assert len(approval.tickets) == 1
    assert result.final_state is TaskState.FAILED
    assert result.failure_reason == "model_error"
