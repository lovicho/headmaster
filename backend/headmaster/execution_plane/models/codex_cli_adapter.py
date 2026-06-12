"""Codex adapter via the local ``codex`` CLI and ChatGPT OAuth session.

The CLI owns ChatGPT sign-in, device auth, token refresh, and credential
storage. Headmaster invokes ``codex exec`` in a read-only, ephemeral run and
normalizes the final assistant message.
"""

import asyncio
import shutil
from collections.abc import Awaitable, Callable

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
    ) -> None:
        self._binary = binary
        self._timeout_s = timeout_s
        self._runner = runner

    def _resolve_binary(self) -> str:
        resolved = shutil.which(self._binary)
        if resolved is None:
            raise ModelGatewayError(
                f"codex CLI not found ('{self._binary}') - install Codex CLI "
                "and run `codex login`"
            )
        return resolved

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
