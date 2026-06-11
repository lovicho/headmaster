"""Phase 1 gate 1-4: both provider adapters pass the SAME contract suite
(LLM-agnostic proof), exercised offline via httpx mock transports."""

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from headmaster.execution_plane.models import (
    AnthropicAdapter,
    FakeAdapter,
    ModelAdapter,
    ModelGateway,
    ModelMessage,
    ModelRequest,
    OpenAIAdapter,
    load_routing,
)
from headmaster.schemas.common import CostTier

REQUEST = ModelRequest(
    messages=[
        ModelMessage(role="system", content="You are a test agent."),
        ModelMessage(role="user", content="Say hello."),
    ],
    cost_tier=CostTier.MINI,
)


def _anthropic_adapter() -> AnthropicAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["system"] == "You are a test agent."
        assert payload["messages"] == [{"role": "user", "content": "Say hello."}]
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "stop_reason": "end_turn",
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.anthropic.com"
    )
    return AnthropicAdapter(api_key="test-key", client=client)


def _openai_adapter() -> OpenAIAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"][0] == {"role": "system", "content": "You are a test agent."}
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {"message": {"content": "hello"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.openai.com"
    )
    return OpenAIAdapter(api_key="test-key", client=client)


@pytest.mark.parametrize(
    "factory",
    [_anthropic_adapter, _openai_adapter],
    ids=["anthropic", "openai"],
)
def test_adapter_contract(factory: Callable[[], ModelAdapter]) -> None:
    """The shared contract: same request in, same normalized response out."""
    adapter = factory()
    response = asyncio.run(adapter.complete(REQUEST, "test-model"))
    assert response.text == "hello"
    assert response.model == "test-model"
    assert response.provider == adapter.provider
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    assert response.stop_reason in {"end_turn", "stop"}


def test_routing_resolution_from_config() -> None:
    routing = load_routing()
    gateway = ModelGateway(routing, {"fake": FakeAdapter()})
    provider, model = gateway.resolve(CostTier.MINI)
    assert provider == "anthropic"
    assert model
    overridden = ModelGateway(routing, {"fake": FakeAdapter()}, provider_override="openai")
    provider, model = overridden.resolve(CostTier.HEAVY)
    assert provider == "openai"
    assert model != "default"  # resolved via alternates table


def test_gateway_dispatches_to_override_adapter() -> None:
    fake = FakeAdapter()
    gateway = ModelGateway(load_routing(), {"fake": fake}, provider_override="fake")
    response = asyncio.run(gateway.complete(REQUEST))
    assert response.provider == "fake"
    assert len(fake.calls) == 1


def test_gateway_unknown_provider_raises() -> None:
    gateway = ModelGateway(load_routing(), {})
    with pytest.raises(KeyError):
        asyncio.run(gateway.complete(REQUEST))
