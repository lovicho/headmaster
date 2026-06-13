"""Claude Code adapter via the local ``claude`` CLI and its OAuth session.

The CLI owns Claude.ai/Anthropic authentication and token refresh. Headmaster
only launches non-interactive print mode and normalizes the returned text.
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
                f"claude CLI not found ('{self._binary}') - install Claude Code "
                "and run `claude auth login`"
            )
        return resolved

    async def probe_environment(self) -> EnvironmentContext:
        """Probe the Claude Code CLI environment.
        
        Returns the version if available and hardcoded native tools.
        """
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
                    # Version usually looks like "@anthropic-ai/claude-code@0.2.29"
                    cli_version = out_text.split("@")[-1] if "@" in out_text else out_text
        except Exception:
            pass  # Fallback to "unknown" on any failure

        base_extension = (
            "You are running within Claude Code CLI.\n"
            "You have access to native CLI tools like `bash`, `file_edit`, etc.\n"
            "Prioritize using them directly for file editing and command execution."
        )
        profile_text = get_profile(self.provider)
        full_extension = f"{base_extension}\n\n{profile_text}" if profile_text else base_extension

        return EnvironmentContext(
            provider_name=self.provider,
            cli_version=cli_version,
            native_capabilities=["mcp", "bash", "file_edit", "glob", "grep", "notebook"],
            system_prompt_extension=full_extension
        )

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
            async with self._semaphore:
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
