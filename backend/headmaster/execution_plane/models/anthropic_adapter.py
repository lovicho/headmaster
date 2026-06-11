"""Anthropic Messages API adapter. API key from ANTHROPIC_API_KEY only."""

import os

import httpx

from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(ModelAdapter):
    provider = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = client or httpx.AsyncClient(
            base_url="https://api.anthropic.com", timeout=120.0
        )

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        response = await self._client.post(
            "/v1/messages",
            json=payload,
            headers={"x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION},
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        return ModelResponse(
            text=text,
            provider=self.provider,
            model=data.get("model", model),
            usage=ModelUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            ),
            stop_reason=data.get("stop_reason"),
        )
