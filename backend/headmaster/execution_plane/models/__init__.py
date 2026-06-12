"""Model gateway and provider adapters — the LLM-agnostic boundary."""

from headmaster.execution_plane.models.agy_cli_adapter import AgyCliAdapter
from headmaster.execution_plane.models.anthropic_adapter import AnthropicAdapter
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
    load_routing,
)
from headmaster.execution_plane.models.gemini_cli_adapter import GeminiCliAdapter
from headmaster.execution_plane.models.openai_adapter import OpenAIAdapter

__all__ = [
    "AgyCliAdapter",
    "AnthropicAdapter",
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
    "load_routing",
]
