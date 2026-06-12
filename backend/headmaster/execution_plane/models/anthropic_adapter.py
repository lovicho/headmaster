"""Anthropic Messages API adapter. API key from ANTHROPIC_API_KEY only.

Tool use is normalized: ToolSpec -> tools[], assistant ToolCalls ->
tool_use blocks, tool results -> tool_result blocks, and tool_use blocks
in responses -> ToolCall objects.
"""

import os

import httpx

from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
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

    @staticmethod
    def _map_messages(request: ModelRequest) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = []
        for m in request.messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                blocks: list[dict[str, object]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.call_id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                    for call in m.tool_calls
                )
                messages.append({"role": "assistant", "content": blocks})
            else:
                messages.append({"role": m.role, "content": m.content})
        return messages

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": self._map_messages(request),
        }
        if system:
            payload["system"] = system
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in request.tools
            ]
        response = await self._client.post(
            "/v1/messages",
            json=payload,
            headers={"x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION},
        )
        response.raise_for_status()
        data = response.json()
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        tool_calls = [
            ToolCall(call_id=b["id"], name=b["name"], arguments=b.get("input", {}))
            for b in blocks
            if b.get("type") == "tool_use"
        ]
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
            tool_calls=tool_calls,
        )
