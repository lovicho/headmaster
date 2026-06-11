"""Phase 2 gate: tool calls outside the harness allowlist are denied."""

import asyncio

import pytest

from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.policy_engine import PolicyEngine, PolicyViolationError
from headmaster.execution_plane.tools import ToolGateway
from headmaster.schemas import AgentHarness, Event, EventType


def _content_harness() -> AgentHarness:
    harness = load_all()["content"]
    assert isinstance(harness, AgentHarness)
    return harness  # allowlist: [rag_search]


def test_policy_engine_allow_and_deny() -> None:
    engine = PolicyEngine()
    harness = _content_harness()
    assert engine.check_tool_call(harness, "rag_search").allowed is True
    denied = engine.check_tool_call(harness, "shell")
    assert denied.allowed is False
    assert "shell" in denied.reason


def test_tool_gateway_denies_and_emits_policy_event() -> None:
    gateway = ToolGateway(PolicyEngine())
    gateway.register("shell", lambda args: "should never run")
    events: list[Event] = []
    with pytest.raises(PolicyViolationError):
        asyncio.run(
            gateway.call(
                harness=_content_harness(),
                tool_name="shell",
                arguments={"cmd": "rm -rf /"},
                task_id="tsk_test",
                emit=events.append,
            )
        )
    assert [e.type for e in events] == [EventType.POLICY_DENIED]
    assert events[0].data["tool"] == "shell"


def test_tool_gateway_executes_allowlisted_tool() -> None:
    gateway = ToolGateway(PolicyEngine())
    gateway.register("rag_search", lambda args: f"results for {args['query']}")
    events: list[Event] = []
    result = asyncio.run(
        gateway.call(
            harness=_content_harness(),
            tool_name="rag_search",
            arguments={"query": "sitemap"},
            task_id="tsk_test",
            emit=events.append,
        )
    )
    assert result == "results for sitemap"
    assert [e.type for e in events] == [EventType.TOOL_CALLED, EventType.TOOL_RESPONDED]


def test_allowlisted_but_unregistered_tool_raises() -> None:
    gateway = ToolGateway(PolicyEngine())
    with pytest.raises(KeyError):
        asyncio.run(
            gateway.call(
                harness=_content_harness(),
                tool_name="rag_search",
                arguments={},
                task_id="tsk_test",
                emit=lambda event: None,
            )
        )
