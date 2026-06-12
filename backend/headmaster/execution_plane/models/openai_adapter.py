"""OpenAI Chat Completions API adapter. API key from OPENAI_API_KEY only.

Tool use is normalized: ToolSpec -> tools[] (function), assistant ToolCalls
-> tool_calls, tool results -> role "tool" messages, and response
tool_calls (JSON-string arguments) -> ToolCall objects.
"""

import json
import os

import httpx

from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
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

    @staticmethod
    def _map_messages(request: ModelRequest) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = []
        for m in request.messages:
            if m.role == "tool":
                messages.append(
                    {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
                )
            elif m.role == "assistant" and m.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": m.content or None,
                        "tool_calls": [
                            {
                                "id": call.call_id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": json.dumps(call.arguments),
                                },
                            }
                            for call in m.tool_calls
                        ],
                    }
                )
            else:
                messages.append({"role": m.role, "content": m.content})
        return messages

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": self._map_messages(request),
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
        response = await self._client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = [
            ToolCall(
                call_id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"].get("arguments") or "{}"),
            )
            for tc in (message.get("tool_calls") or [])
        ]
        usage = data.get("usage", {})
        return ModelResponse(
            text=message.get("content") or "",
            provider=self.provider,
            model=data.get("model", model),
            usage=ModelUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
            stop_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
        )
