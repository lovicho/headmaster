"""Policy engine — deterministic first-class controls, not prompt filters.

Phase 2 scope: tool-call allowlist enforcement per harness tool_policy.
Risk-tier action policies and approval routing arrive in Phase 3.
"""

from pydantic import BaseModel

from headmaster.schemas.harness_manifest import AgentHarness


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str


class PolicyViolationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PolicyEngine:
    def check_tool_call(self, harness: AgentHarness, tool_name: str) -> PolicyDecision:
        allowlist = harness.tool_policy.mcp_allowed
        if tool_name in allowlist:
            return PolicyDecision(allowed=True, reason=f"'{tool_name}' is allowlisted")
        return PolicyDecision(
            allowed=False,
            reason=(
                f"tool '{tool_name}' is not in the allowlist of harness"
                f" '{harness.harness_id}' (allowed: {sorted(allowlist)})"
            ),
        )
