"""Tool gateway — policy-enforced tool execution boundary."""

from headmaster.execution_plane.tools.builtin import build_default_tool_gateway
from headmaster.execution_plane.tools.mcp import (
    McpStdioServerConfig,
    McpTransportError,
    discover_mcp_stdio_tools,
    load_mcp_stdio_configs,
    register_mcp_stdio_server,
)
from headmaster.execution_plane.tools.tool_gateway import ToolGateway

__all__ = [
    "McpStdioServerConfig",
    "McpTransportError",
    "ToolGateway",
    "build_default_tool_gateway",
    "discover_mcp_stdio_tools",
    "load_mcp_stdio_configs",
    "register_mcp_stdio_server",
]
