"""ModelGateway — the single LLM-agnostic interface.

Harnesses declare a cost tier only; this gateway resolves tier -> provider/model
from config/models.yaml and delegates to the provider adapter. Provider-specific
request/response shapes never leak past the adapters.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, Field

from headmaster.schemas.common import CostTier

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


class ToolSpec(BaseModel):
    """Provider-agnostic tool declaration offered to the model."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})


class ToolCall(BaseModel):
    """Normalized tool invocation requested by the model."""

    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)  # assistant turns
    tool_call_id: str | None = None  # tool-result turns


class ModelRequest(BaseModel):
    messages: list[ModelMessage]
    cost_tier: CostTier = CostTier.MINI
    max_tokens: int = 4096
    temperature: float = 0.2
    tools: list[ToolSpec] = Field(default_factory=list)


class ModelUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ModelResponse(BaseModel):
    text: str
    provider: str
    model: str
    usage: ModelUsage = Field(default_factory=ModelUsage)
    stop_reason: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ModelGatewayError(Exception):
    """Transient or provider-level model failure — recoverable by the orchestrator."""


class ModelAdapter(ABC):
    """Contract every provider adapter must satisfy (verified by a shared test suite)."""

    provider: ClassVar[str]

    @abstractmethod
    async def complete(self, request: ModelRequest, model: str) -> ModelResponse: ...


class TierRoute(BaseModel):
    provider: str
    model: str


class ModelRoutingConfig(BaseModel):
    default_provider: str
    tiers: dict[CostTier, TierRoute]
    alternates: dict[str, dict[CostTier, str]] = Field(default_factory=dict)


def load_routing(path: Path | None = None) -> ModelRoutingConfig:
    config_path = path or (CONFIG_DIR / "models.yaml")
    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ModelRoutingConfig.model_validate(raw)


class ModelGateway:
    def __init__(
        self,
        routing: ModelRoutingConfig,
        adapters: dict[str, ModelAdapter],
        provider_override: str | None = None,
    ) -> None:
        self._routing = routing
        self._adapters = adapters
        self._provider_override = provider_override

    def resolve(self, tier: CostTier) -> tuple[str, str]:
        """Resolve a cost tier to (provider, model) honoring any provider override."""
        route = self._routing.tiers[tier]
        provider = self._provider_override or route.provider
        if provider == route.provider:
            return provider, route.model
        alternate = self._routing.alternates.get(provider)
        if alternate and tier in alternate:
            return provider, alternate[tier]
        return provider, "default"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        provider, model = self.resolve(request.cost_tier)
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise KeyError(f"no adapter registered for provider: {provider}")
        try:
            return await adapter.complete(request, model)
        except ModelGatewayError:
            raise
        except Exception as err:
            raise ModelGatewayError(f"{provider}/{model}: {err}") from err
