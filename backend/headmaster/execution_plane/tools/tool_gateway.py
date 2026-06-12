"""Tool gateway — every tool call passes the policy engine first and is
fully event-logged. Local callables now; the MCP transport plugs in behind
this same boundary later.
"""

import inspect
from collections.abc import Callable

from headmaster.control_plane.policy_engine import PolicyEngine, PolicyViolationError
from headmaster.execution_plane.models.gateway import ToolSpec
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness

EmitFn = Callable[[Event], None]
ToolFn = Callable[[dict[str, object]], object]

SOURCE = "headmaster.tool_gateway"


class ToolGateway:
    def __init__(self, policy: PolicyEngine) -> None:
        self._policy = policy
        self._tools: dict[str, tuple[ToolFn, ToolSpec]] = {}

    def register(
        self,
        name: str,
        fn: ToolFn,
        *,
        description: str = "",
        input_schema: dict[str, object] | None = None,
    ) -> None:
        spec = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
        )
        self._tools[name] = (fn, spec)

    def specs_for(self, harness: AgentHarness) -> list[ToolSpec]:
        """Tools offered to the model: registered AND allowlisted for this harness."""
        return [
            spec
            for name, (_, spec) in sorted(self._tools.items())
            if name in harness.tool_policy.mcp_allowed
        ]

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

        registered = self._tools.get(tool_name)
        if registered is None:
            raise KeyError(f"tool '{tool_name}' is allowlisted but not registered")
        fn, _ = registered
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
