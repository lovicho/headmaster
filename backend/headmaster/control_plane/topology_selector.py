"""Topology selector — conditional orchestration (2nd report).

Not every task deserves a multi-agent orchestra: the level is chosen from
risk and shape of the task. Execution of the multi-agent levels lands in
Phase 3; the decision contract is fixed here.
"""

from enum import StrEnum

from pydantic import BaseModel

from headmaster.schemas.common import RiskLevel
from headmaster.schemas.harness_manifest import AgentHarness
from headmaster.schemas.task_spec import TaskSpec


class OrchestrationLevel(StrEnum):
    SINGLE_HOP = "single_hop"
    SINGLE_AGENT_WITH_TOOLS = "single_agent_with_tools"
    MULTI_AGENT_SUPERVISED = "multi_agent_supervised"
    MULTI_AGENT_WITH_HITL = "multi_agent_with_hitl"


class TopologyDecision(BaseModel):
    level: OrchestrationLevel
    reason: str


def select_topology(
    spec: TaskSpec,
    harness: AgentHarness,
    *,
    decomposable: bool = False,
) -> TopologyDecision:
    if spec.risk_profile.needs_human_approval or spec.risk_profile.action_risk is RiskLevel.HIGH:
        return TopologyDecision(
            level=OrchestrationLevel.MULTI_AGENT_WITH_HITL,
            reason="high action risk or explicit human approval requirement",
        )
    if decomposable:
        return TopologyDecision(
            level=OrchestrationLevel.MULTI_AGENT_SUPERVISED,
            reason="task decomposes into parallelizable subtasks",
        )
    if harness.tool_policy.mcp_allowed:
        return TopologyDecision(
            level=OrchestrationLevel.SINGLE_AGENT_WITH_TOOLS,
            reason="single agent suffices but tools are required",
        )
    return TopologyDecision(
        level=OrchestrationLevel.SINGLE_HOP,
        reason="simple task — no tools, no decomposition, low risk",
    )
