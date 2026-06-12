"""Phase 4d: agent tool-use loop — policed tool calls with model feedback."""

import asyncio

from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentDraft, AgentRuntime
from headmaster.execution_plane.memory import MemoryFabric
from headmaster.execution_plane.models import (
    FakeAdapter,
    ModelGateway,
    ToolCall,
    load_routing,
)
from headmaster.execution_plane.tools import ToolGateway, build_default_tool_gateway
from headmaster.schemas import (
    AgentHarness,
    Event,
    EventType,
    IBFRequirements,
    MemoryRecord,
    MemoryScope,
)
from headmaster.tests.test_orchestrator import VALID_RESPONSE


def _content_harness() -> AgentHarness:
    harness = load_all()["content"]
    assert isinstance(harness, AgentHarness)
    return harness  # allowlist: [rag_search]


def _fabric_with_asset() -> MemoryFabric:
    fabric = MemoryFabric()
    fabric.write(
        MemoryRecord(scope=MemoryScope.SKILL, summary="proven hero template for B2B")
    )
    return fabric


def _run(
    fake: FakeAdapter, tool_gateway: ToolGateway
) -> tuple[AgentDraft, list[Event]]:
    gateway = ModelGateway(load_routing(), {"fake": fake}, provider_override="fake")
    runtime = AgentRuntime(gateway, tool_gateway=tool_gateway)
    events: list[Event] = []
    draft = asyncio.run(
        runtime.run(
            harness=_content_harness(),
            task=compile_task("툴 루프 테스트 작업"),
            requirements=IBFRequirements(),
            revision_notes=[],
            emit=events.append,
        )
    )
    return draft, events


def test_tool_loop_executes_and_feeds_result_back() -> None:
    tool_gateway = build_default_tool_gateway(_fabric_with_asset())
    fake = FakeAdapter(
        [
            [ToolCall(call_id="t1", name="rag_search", arguments={"query": "hero"})],
            VALID_RESPONSE,
        ]
    )
    draft, events = _run(fake, tool_gateway)

    types = [e.type for e in events]
    assert types.count(EventType.MODEL_CALLED) == 2
    assert EventType.TOOL_CALLED in types
    assert EventType.TOOL_RESPONDED in types

    # the model was offered exactly the allowlisted+registered tools
    assert [tool.name for tool in fake.calls[0].tools] == ["rag_search"]
    # the tool result was fed back as a tool-role message
    second_request = fake.calls[1]
    tool_messages = [m for m in second_request.messages if m.role == "tool"]
    assert tool_messages and "proven hero template" in tool_messages[0].content
    assert tool_messages[0].tool_call_id == "t1"
    assistant_turns = [m for m in second_request.messages if m.tool_calls]
    assert assistant_turns and assistant_turns[0].tool_calls[0].name == "rag_search"

    # usage is summed across rounds (2 fake calls x 100/50)
    assert draft.usage.input_tokens == 200
    assert draft.usage.output_tokens == 100
    assert draft.bundle.ibf_proof is not None


def test_denied_tool_feeds_policy_denial_back_to_model() -> None:
    tool_gateway = build_default_tool_gateway(_fabric_with_asset())
    fake = FakeAdapter(
        [
            [ToolCall(call_id="t1", name="shell", arguments={"cmd": "rm -rf /"})],
            VALID_RESPONSE,
        ]
    )
    draft, events = _run(fake, tool_gateway)

    types = [e.type for e in events]
    assert EventType.POLICY_DENIED in types
    assert EventType.TOOL_RESPONDED not in types  # the tool never executed
    tool_messages = [m for m in fake.calls[1].messages if m.role == "tool"]
    assert tool_messages and tool_messages[0].content.startswith("DENIED by policy")
    # the run still converges to a final deliverable
    assert draft.bundle.ibf_proof is not None


def test_tool_round_budget_is_bounded() -> None:
    tool_gateway = build_default_tool_gateway(_fabric_with_asset())
    endless_call = [ToolCall(call_id="t", name="rag_search", arguments={"query": "x"})]
    fake = FakeAdapter([endless_call] * 10 + [VALID_RESPONSE])
    runtime_rounds = 2
    gateway = ModelGateway(load_routing(), {"fake": fake}, provider_override="fake")
    runtime = AgentRuntime(gateway, tool_gateway=tool_gateway, max_tool_rounds=runtime_rounds)
    events: list[Event] = []
    draft = asyncio.run(
        runtime.run(
            harness=_content_harness(),
            task=compile_task("바운드 테스트"),
            requirements=IBFRequirements(),
            revision_notes=[],
            emit=events.append,
        )
    )
    # rounds are capped: initial call + max_tool_rounds follow-ups
    assert len(fake.calls) == runtime_rounds + 1
    # final response was a tool_call that we refused to execute -> draft has no proof
    assert draft.bundle.ibf_proof is None
