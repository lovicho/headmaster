"""Gemini adapter via the local gemini CLI — OAuth, no API key.

The CLI owns the OAuth flow and token refresh (~/.gemini/oauth_creds.json,
auth type "oauth-personal"). Headless calls disable MCP servers and
extensions so startup is fast and deterministic. Model "default" delegates
model choice to the CLI.
"""

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

from headmaster.execution_plane.concurrency_config import DEFAULT_CONCURRENCY_LIMIT
from headmaster.execution_plane.models.gateway import (
    ModelAdapter,
    ModelGatewayError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from headmaster.schemas.environment import EnvironmentContext
from headmaster.execution_plane.models.provider_profiles import get_profile

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


def _extract_usage(stats: dict[str, Any]) -> ModelUsage:
    """Best-effort token extraction from `-o json` stats (shape varies by version)."""
    prompt_tokens = 0
    output_tokens = 0
    models = stats.get("models")
    if isinstance(models, dict):
        for model_stats in models.values():
            if not isinstance(model_stats, dict):
                continue
            tokens = model_stats.get("tokens", {})
            if isinstance(tokens, dict):
                prompt_tokens += int(tokens.get("prompt", 0) or 0)
                output_tokens += int(tokens.get("candidates", 0) or 0)
    return ModelUsage(input_tokens=prompt_tokens, output_tokens=output_tokens)


async def _subprocess_runner(args: list[str]) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout, stderr


class GeminiCliAdapter(ModelAdapter):
    provider = "gemini"

    def __init__(
        self,
        binary: str = "gemini",
        timeout_s: float = 300.0,
        runner: Runner | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self._binary = binary
        self._timeout_s = timeout_s
        self._runner = runner
        limit = max_concurrent if max_concurrent is not None else DEFAULT_CONCURRENCY_LIMIT
        self._semaphore = asyncio.Semaphore(limit)

    def _resolve_binary(self) -> str:
        resolved = shutil.which(self._binary)
        if resolved is None:
            raise ModelGatewayError(
                f"gemini CLI not found ('{self._binary}') — install it and run OAuth login"
            )
        return resolved

    async def probe_environment(self) -> EnvironmentContext:
        """Probe the Gemini CLI environment."""
        cli_version = "unknown"
        try:
            binary = self._resolve_binary() if self._runner is None else self._binary
            runner = self._runner or _subprocess_runner
            async with self._semaphore:
                returncode, stdout, _ = await asyncio.wait_for(
                    runner([binary, "--version"]), timeout=10.0
                )
            if returncode == 0:
                out_text = stdout.decode("utf-8", errors="replace").strip()
                if out_text:
                    cli_version = out_text
        except Exception:
            pass

        base_extension = (
            "You are running within Gemini CLI environment.\n"
        )
        profile_text = get_profile(self.provider)
        full_extension = f"{base_extension}\n\n{profile_text}" if profile_text else base_extension

        return EnvironmentContext(
            provider_name=self.provider,
            cli_version=cli_version,
            native_capabilities=["search", "mcp"],
            system_prompt_extension=full_extension
        )

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        args = [
            self._resolve_binary() if self._runner is None else self._binary,
            "-p",
            _compose_prompt(request),
            "-o",
            "json",
            "--allowed-mcp-server-names",
            "__none__",
            "-e",
            "none",
        ]
        if model and model != "default":
            args.extend(["-m", model])
        runner = self._runner or _subprocess_runner
        try:
            async with self._semaphore:
                returncode, stdout, stderr = await asyncio.wait_for(
                    runner(args), timeout=self._timeout_s
                )
        except TimeoutError as err:
            raise ModelGatewayError(
                f"gemini CLI timed out after {self._timeout_s}s"
            ) from err
        out_text = stdout.decode("utf-8", errors="replace").strip()
        if returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            raise ModelGatewayError(
                f"gemini CLI exited {returncode}: {err_text[-500:] or out_text[-500:]}"
            )

        text = out_text
        usage = ModelUsage()
        resolved_model = model
        start = out_text.find("{")
        if start >= 0:
            try:
                data = json.loads(out_text[start:])
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict) and "response" in data:
                text = str(data.get("response", ""))
                stats = data.get("stats")
                if isinstance(stats, dict):
                    usage = _extract_usage(stats)
                    models = stats.get("models")
                    if isinstance(models, dict) and models:
                        resolved_model = next(iter(models))
        return ModelResponse(
            text=text,
            provider=self.provider,
            model=resolved_model,
            usage=usage,
            stop_reason="end_turn",
        )
