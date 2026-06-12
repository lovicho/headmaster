"""MCP stdio transport integration tests."""

import asyncio
import sys
from pathlib import Path

from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.policy_engine import PolicyEngine
from headmaster.execution_plane.tools import (
    McpStdioServerConfig,
    ToolGateway,
    discover_mcp_stdio_tools,
    load_mcp_stdio_configs,
    register_mcp_stdio_server,
)
from headmaster.schemas import AgentHarness, Event, EventType

FIXTURE_SERVER = Path(__file__).resolve().parent / "fixtures" / "mcp_echo_server.py"


def _config() -> McpStdioServerConfig:
    return McpStdioServerConfig(
        name="echo",
        command=sys.executable,
        args=[str(FIXTURE_SERVER)],
        timeout_seconds=3,
    )


def _harness_with_mcp_tool(tool_name: str) -> AgentHarness:
    harness = load_all()["content"]
    assert isinstance(harness, AgentHarness)
    return harness.model_copy(
        update={
            "tool_policy": harness.tool_policy.model_copy(
                update={"mcp_allowed": [tool_name]}
            )
        }
    )


def test_discover_mcp_stdio_tools() -> None:
    mappings = asyncio.run(discover_mcp_stdio_tools(_config()))

    assert len(mappings) == 1
    assert mappings[0].public_name == "mcp_echo_echo"
    assert mappings[0].remote_name == "echo"
    assert mappings[0].spec.input_schema["required"] == ["message"]


def test_register_mcp_stdio_server_executes_through_tool_gateway() -> None:
    gateway = ToolGateway(PolicyEngine())
    mappings = asyncio.run(register_mcp_stdio_server(gateway, _config()))
    harness = _harness_with_mcp_tool(mappings[0].public_name)
    events: list[Event] = []

    result = asyncio.run(
        gateway.call(
            harness=harness,
            tool_name="mcp_echo_echo",
            arguments={"message": "hello"},
            task_id="tsk_mcp",
            emit=events.append,
        )
    )

    assert result == "echo: hello"
    assert [spec.name for spec in gateway.specs_for(harness)] == ["mcp_echo_echo"]
    assert [event.type for event in events] == [
        EventType.TOOL_CALLED,
        EventType.TOOL_RESPONDED,
    ]


def test_load_mcp_stdio_configs(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        """
        {
          "servers": [
            {
              "name": "echo",
              "command": "python",
              "args": ["server.py"],
              "tool_prefix": "custom"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    configs = load_mcp_stdio_configs(config_path)

    assert configs[0].name == "echo"
    assert configs[0].public_prefix == "custom"
