"""Claude Code adapter via the local ``claude`` CLI and its OAuth session.

The CLI owns Claude.ai/Anthropic authentication and token refresh. Headmaster
only launches non-interactive print mode and normalizes the returned text.
"""

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelGatewayError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)

Runner = Callable[[list[str]], Awaitable[tuple[int, bytes, bytes]]]


def _compose_prompt(request: ModelRequest) -> str:
    sections: list[str] = []
    for message in request.messages:
        if message.role == "system":
            sections.append(f"[SYSTEM INSTRUCTIONS]\n{message.content}")
        elif message.role == "user":
            sections.append(f"[USER]\n{message.content}")
        else:
            sections.append(f"[{message.role.upper()}]\n{message.content}")
    return "\n\n".join(sections)


def _usage_from_json(data: dict[str, Any]) -> ModelUsage:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return ModelUsage()
    return ModelUsage(
        input_tokens=int(
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("input")
            or 0
        ),
        output_tokens=int(
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("output")
            or 0
        ),
    )


async def _subprocess_runner(args: list[str]) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout, stderr


class ClaudeCodeCliAdapter(ModelAdapter):
    provider = "claude"

    def __init__(
        self,
        binary: str = "claude",
        timeout_s: float = 600.0,
        runner: Runner | None = None,
    ) -> None:
        self._binary = binary
        self._timeout_s = timeout_s
        self._runner = runner

    def _resolve_binary(self) -> str:
        resolved = shutil.which(self._binary)
        if resolved is None:
            raise ModelGatewayError(
                f"claude CLI not found ('{self._binary}') - install Claude Code "
                "and run `claude auth login`"
            )
        return resolved

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        args = [
            self._resolve_binary() if self._runner is None else self._binary,
            "-p",
            _compose_prompt(request),
            "--output-format",
            "json",
            "--no-session-persistence",
            "--tools",
            "",
            "--disallowedTools",
            "*",
        ]
        if model and model != "default":
            args.extend(["--model", model])
        runner = self._runner or _subprocess_runner
        try:
            returncode, stdout, stderr = await asyncio.wait_for(
                runner(args), timeout=self._timeout_s
            )
        except TimeoutError as err:
            raise ModelGatewayError(
                f"claude CLI timed out after {self._timeout_s}s"
            ) from err

        out_text = stdout.decode("utf-8", errors="replace").strip()
        if returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            raise ModelGatewayError(
                f"claude CLI exited {returncode}: {err_text[-500:] or out_text[-500:]}"
            )
        try:
            data = json.loads(out_text)
        except json.JSONDecodeError as err:
            raise ModelGatewayError("claude CLI did not return JSON output") from err
        if not isinstance(data, dict):
            raise ModelGatewayError("claude CLI returned an unexpected JSON payload")

        raw_result = data.get("result") or data.get("text") or data.get("content")
        text = raw_result if isinstance(raw_result, str) else ""
        if not text.strip():
            raise ModelGatewayError("claude CLI produced no response text")
        resolved_model = data.get("model")
        return ModelResponse(
            text=text,
            provider=self.provider,
            model=resolved_model if isinstance(resolved_model, str) else model,
            usage=_usage_from_json(data),
            stop_reason="end_turn",
        )
