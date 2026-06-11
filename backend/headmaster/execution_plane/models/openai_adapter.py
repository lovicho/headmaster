"""OpenAI Chat Completions API adapter. API key from OPENAI_API_KEY only."""

import os

import httpx

from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


class OpenAIAdapter(ModelAdapter):
    provider = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = client or httpx.AsyncClient(
            base_url="https://api.openai.com", timeout=120.0
        )

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        response = await self._client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        usage = data.get("usage", {})
        return ModelResponse(
            text=choice.get("message", {}).get("content", ""),
            provider=self.provider,
            model=data.get("model", model),
            usage=ModelUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
            stop_reason=choice.get("finish_reason"),
        )
