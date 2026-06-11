"""Phase 2: conditional orchestration levels (2nd report)."""

from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.topology_selector import OrchestrationLevel, select_topology
from headmaster.schemas import AgentHarness, RiskLevel, RiskProfile, TaskSpec


def _harness(harness_id: str) -> AgentHarness:
    harness = load_all()[harness_id]
    assert isinstance(harness, AgentHarness)
    return harness


def _spec(**risk: object) -> TaskSpec:
    return TaskSpec(
        title="t", intent="t", risk_profile=RiskProfile.model_validate(risk)
    )


def test_hitl_for_human_approval_flag() -> None:
    decision = select_topology(_spec(needs_human_approval=True), _harness("content"))
    assert decision.level is OrchestrationLevel.MULTI_AGENT_WITH_HITL


def test_hitl_for_high_action_risk() -> None:
    decision = select_topology(_spec(action_risk=RiskLevel.HIGH), _harness("consultant"))
    assert decision.level is OrchestrationLevel.MULTI_AGENT_WITH_HITL


def test_supervised_for_decomposable_task() -> None:
    decision = select_topology(_spec(), _harness("content"), decomposable=True)
    assert decision.level is OrchestrationLevel.MULTI_AGENT_SUPERVISED


def test_single_agent_with_tools() -> None:
    decision = select_topology(_spec(), _harness("content"))  # allowlist non-empty
    assert decision.level is OrchestrationLevel.SINGLE_AGENT_WITH_TOOLS


def test_single_hop_for_toolless_low_risk() -> None:
    decision = select_topology(_spec(), _harness("consultant"))  # empty allowlist
    assert decision.level is OrchestrationLevel.SINGLE_HOP
