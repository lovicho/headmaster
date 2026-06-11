"""Tool gateway — every tool call passes the policy engine first and is
fully event-logged. Local callables now; the MCP transport plugs in behind
this same boundary later.
"""

import inspect
from collections.abc import Callable

from headmaster.control_plane.policy_engine import PolicyEngine, PolicyViolationError
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness

EmitFn = Callable[[Event], None]
ToolFn = Callable[[dict[str, object]], object]

SOURCE = "headmaster.tool_gateway"


class ToolGateway:
    def __init__(self, policy: PolicyEngine) -> None:
        self._policy = policy
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    async def call(
        self,
        *,
        harness: AgentHarness,
        tool_name: str,
        arguments: dict[str, object],
        task_id: str,
        emit: EmitFn,
    ) -> object:
        decision = self._policy.check_tool_call(harness, tool_name)
        if not decision.allowed:
            emit(
                Event(
                    source=SOURCE,
                    type=EventType.POLICY_DENIED,
                    subject=task_id,
                    data={
                        "agent": harness.harness_id,
                        "tool": tool_name,
                        "reason": decision.reason,
                    },
                )
            )
            raise PolicyViolationError(decision.reason)

        fn = self._tools.get(tool_name)
        if fn is None:
            raise KeyError(f"tool '{tool_name}' is allowlisted but not registered")
        emit(
            Event(
                source=SOURCE,
                type=EventType.TOOL_CALLED,
                subject=task_id,
                data={"agent": harness.harness_id, "tool": tool_name, "arguments": arguments},
            )
        )
        result = fn(arguments)
        if inspect.isawaitable(result):
            result = await result
        emit(
            Event(
                source=SOURCE,
                type=EventType.TOOL_RESPONDED,
                subject=task_id,
                data={"agent": harness.harness_id, "tool": tool_name, "result": str(result)},
            )
        )
        return result
