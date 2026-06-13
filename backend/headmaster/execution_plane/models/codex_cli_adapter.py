"""Codex adapter via the local ``codex`` CLI and ChatGPT OAuth session.

The CLI owns ChatGPT sign-in, device auth, token refresh, and credential
storage. Headmaster invokes ``codex exec`` in a read-only, ephemeral run and
normalizes the final assistant message.
"""

import asyncio
import shutil
from collections.abc import Awaitable, Callable

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


async def _subprocess_runner(args: list[str]) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout, stderr


class CodexCliAdapter(ModelAdapter):
    provider = "codex"

    def __init__(
        self,
        binary: str = "codex",
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
                f"codex CLI not found ('{self._binary}') - install Codex CLI "
                "and run `codex login`"
            )
        return resolved

    async def probe_environment(self) -> EnvironmentContext:
        """Probe the Codex CLI environment."""
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
            pass  # Fallback to "unknown"

        base_extension = (
            "You are running within Codex CLI environment.\n"
            "You have access to strong repository analysis and code generation abilities."
        )
        profile_text = get_profile(self.provider)
        full_extension = f"{base_extension}\n\n{profile_text}" if profile_text else base_extension

        return EnvironmentContext(
            provider_name=self.provider,
            cli_version=cli_version,
            native_capabilities=["codegen", "repository_analysis", "test_generation"],
            system_prompt_extension=full_extension
        )

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        args = [
            self._resolve_binary() if self._runner is None else self._binary,
            "exec",
            "--ephemeral",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "--skip-git-repo-check",
            "--color",
            "never",
        ]
        if model and model != "default":
            args.extend(["--model", model])
        args.append(_compose_prompt(request))

        runner = self._runner or _subprocess_runner
        try:
            async with self._semaphore:
                returncode, stdout, stderr = await asyncio.wait_for(
                    runner(args), timeout=self._timeout_s
                )
        except TimeoutError as err:
            raise ModelGatewayError(
                f"codex CLI timed out after {self._timeout_s}s"
            ) from err

        out_text = stdout.decode("utf-8", errors="replace").strip()
        if returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            raise ModelGatewayError(
                f"codex CLI exited {returncode}: {err_text[-500:] or out_text[-500:]}"
            )
        if not out_text:
            raise ModelGatewayError("codex CLI produced no response text")
        return ModelResponse(
            text=out_text,
            provider=self.provider,
            model=model,
            usage=ModelUsage(),
            stop_reason="end_turn",
        )
