"""Antigravity (agy) adapter — Google OAuth via the local agy CLI, no API key.

agy only renders output to a real terminal, so the adapter hosts it inside
a ConPTY pseudo-terminal (pywinpty, Windows-only) and scrapes the response:
ANSI/OSC control sequences are stripped and the residual plain text is the
model reply. stdin is the pty, the prompt travels via ``-p``; a very wide
pty prevents mid-line wrapping that would corrupt JSON strings.
"""

import asyncio
import re
import time
from collections.abc import Callable
from pathlib import Path

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

# OSC (terminated by BEL or ST), CSI, and single-char escapes
_ANSI = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL|ST
    r"|\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI
    r"|\x1b[@-Z\\-_]"  # single ESC sequences
)

Runner = Callable[[list[str] | str, float], str]


def strip_terminal_noise(raw: str) -> str:
    return _ANSI.sub("", raw).replace("\r", "").strip()


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


def _isolated_cwd() -> str:
    """agy attaches to the workspace of its cwd; run it from an empty temp dir
    so it never joins an active Antigravity IDE conversation or reads repo files."""
    import tempfile

    workdir = Path(tempfile.gettempdir()) / "headmaster-agy"
    workdir.mkdir(parents=True, exist_ok=True)
    return str(workdir)


def _conpty_runner(args: list[str] | str, timeout_s: float) -> str:
    from winpty import PtyProcess  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: I001

    process = PtyProcess.spawn(args, dimensions=(120, 9000), cwd=_isolated_cwd())
    chunks: list[str] = []
    deadline = time.monotonic() + timeout_s
    try:
        while process.isalive():
            if time.monotonic() > deadline:
                raise ModelGatewayError(f"agy CLI timed out after {timeout_s}s")
            try:
                chunks.append(process.read(8192))
            except (EOFError, ConnectionAbortedError):
                break
    finally:
        if process.isalive():
            process.terminate(force=True)
    return "".join(chunks)


class AgyCliAdapter(ModelAdapter):
    provider = "agy"

    def __init__(
        self,
        binary: str = "agy.exe",
        timeout_s: float = 600.0,
        runner: Runner | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self._binary = binary
        self._timeout_s = timeout_s
        self._runner = runner
        limit = max_concurrent if max_concurrent is not None else DEFAULT_CONCURRENCY_LIMIT
        self._semaphore = asyncio.Semaphore(limit)

    async def probe_environment(self) -> EnvironmentContext:
        """Probe the Antigravity (AGY) CLI environment."""
        cli_version = "unknown"
        try:
            # Simple subprocess for version check (pty not needed for just --version)
            async with self._semaphore:
                process = await asyncio.create_subprocess_exec(
                    self._binary, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)
            if process.returncode == 0:
                out_text = strip_terminal_noise(stdout.decode("utf-8", errors="replace")).strip()
                if out_text:
                    cli_version = out_text
        except Exception:
            pass  # Fallback to "unknown"

        base_extension = (
            "You are running within the Antigravity (AGY) environment.\n"
            "You have access to advanced Google Antigravity SDK features."
        )
        profile_text = get_profile(self.provider)
        full_extension = f"{base_extension}\n\n{profile_text}" if profile_text else base_extension

        return EnvironmentContext(
            provider_name=self.provider,
            cli_version=cli_version,
            native_capabilities=[
                "multi_agent_orchestration",
                "google_antigravity_sdk",
                "local_mcp"
            ],
            system_prompt_extension=full_extension
        )

    async def complete(self, request: ModelRequest, model: str) -> ModelResponse:
        args = [self._binary, "-p", _compose_prompt(request)]
        if model and model != "default":
            args.extend(["--model", model])
        runner = self._runner or _conpty_runner
        async with self._semaphore:
            raw = await asyncio.to_thread(runner, args, self._timeout_s)
        text = strip_terminal_noise(raw)
        if not text:
            raise ModelGatewayError("agy CLI produced no response text")
        return ModelResponse(
            text=text,
            provider=self.provider,
            model=model or "default",
            usage=ModelUsage(),  # agy does not expose token counts
            stop_reason="end_turn",
        )
