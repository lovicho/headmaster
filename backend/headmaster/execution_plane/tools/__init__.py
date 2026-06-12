"""Tool gateway — policy-enforced tool execution boundary."""

from headmaster.execution_plane.tools.builtin import build_default_tool_gateway
from headmaster.execution_plane.tools.tool_gateway import ToolGateway

__all__ = ["ToolGateway", "build_default_tool_gateway"]
