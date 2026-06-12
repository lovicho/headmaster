"""Model gateway and provider adapters — the LLM-agnostic boundary."""

from headmaster.execution_plane.models.agy_cli_adapter import AgyCliAdapter
from headmaster.execution_plane.models.anthropic_adapter import AnthropicAdapter
from headmaster.execution_plane.models.claude_code_cli_adapter import ClaudeCodeCliAdapter
from headmaster.execution_plane.models.codex_cli_adapter import CodexCliAdapter
from headmaster.execution_plane.models.fake_adapter import FakeAdapter
from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelGateway,
    ModelGatewayError,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRoutingConfig,
    ModelUsage,
    TierRoute,
    ToolCall,
    ToolSpec,
    load_routing,
)
from headmaster.execution_plane.models.gemini_cli_adapter import GeminiCliAdapter
from headmaster.execution_plane.models.openai_adapter import OpenAIAdapter

__all__ = [
    "AgyCliAdapter",
    "AnthropicAdapter",
    "ClaudeCodeCliAdapter",
    "CodexCliAdapter",
    "FakeAdapter",
    "GeminiCliAdapter",
    "ModelAdapter",
    "ModelGateway",
    "ModelGatewayError",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ModelRoutingConfig",
    "ModelUsage",
    "OpenAIAdapter",
    "TierRoute",
    "ToolCall",
    "ToolSpec",
    "load_routing",
]
