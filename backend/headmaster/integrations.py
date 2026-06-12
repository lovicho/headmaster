"""Install agent-CLI integration scaffolds for Headmaster."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

SUPPORTED_TOOLS = ("claude", "codex", "agy")


@dataclass(frozen=True)
class IntegrationFile:
    """A file that should be written for an agent CLI integration."""

    path: Path
    content: str
    tool: str
    description: str


@dataclass(frozen=True)
class IntegrationWrite:
    """Result of writing one integration file."""

    path: Path
    status: str
    tool: str


def parse_tools(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated tool list."""

    if raw is None or raw.strip().lower() == "all":
        return SUPPORTED_TOOLS
    requested = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    unknown = sorted(set(requested) - set(SUPPORTED_TOOLS))
    if unknown:
        raise ValueError(f"unknown integration tool(s): {', '.join(unknown)}")
    if not requested:
        raise ValueError("at least one integration tool is required")
    return requested


def build_integration_files(
    *,
    scope: str,
    root: Path,
    tools: tuple[str, ...],
    home: Path | None = None,
) -> list[IntegrationFile]:
    """Build the files needed for project- or user-scoped integrations."""

    if scope not in {"project", "user"}:
        raise ValueError("scope must be 'project' or 'user'")
    base = root.resolve() if scope == "project" else (home or Path.home()).resolve()
    files: list[IntegrationFile] = []

    if "claude" in tools:
        claude_skill = base / ".claude" / "skills" / "haema" / "SKILL.md"
        files.append(
            IntegrationFile(
                path=claude_skill,
                content=claude_skill_content(),
                tool="claude",
                description="Claude Code /haema skill",
            )
        )
        files.append(
            IntegrationFile(
                path=base / ".claude" / "commands" / "haema.md",
                content=claude_command_content(),
                tool="claude",
                description="Claude Code legacy /haema command",
            )
        )

    if "codex" in tools:
        files.append(
            IntegrationFile(
                path=base / ".agents" / "skills" / "haema" / "SKILL.md",
                content=agent_skill_content(),
                tool="codex",
                description="Codex Agent Skills /haema workflow",
            )
        )

    if "agy" in tools:
        files.append(
            IntegrationFile(
                path=base / ".agent" / "skills" / "haema" / "SKILL.md",
                content=agent_skill_content(),
                tool="agy",
                description="Antigravity Agent Skills /haema workflow",
            )
        )

    if scope == "user" and "codex" in tools:
        files.append(
            IntegrationFile(
                path=base / ".codex" / "prompts" / "haema.md",
                content=codex_prompt_content(),
                tool="codex",
                description="Codex deprecated /prompts:haema fallback",
            )
        )

    if scope == "user" and "agy" in tools:
        files.append(
            IntegrationFile(
                path=base / ".gemini" / "antigravity" / "skills" / "haema" / "SKILL.md",
                content=agent_skill_content(),
                tool="agy",
                description="Antigravity global Agent Skills workflow",
            )
        )

    return files


def write_integration_files(
    files: list[IntegrationFile], *, force: bool = False
) -> list[IntegrationWrite]:
    """Write integration files idempotently."""

    writes: list[IntegrationWrite] = []
    for file in files:
        path = file.path
        status = "installed"
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == file.content:
                status = "unchanged"
            elif not force:
                writes.append(IntegrationWrite(path=path, status="skipped", tool=file.tool))
                continue
            else:
                status = "updated"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content, encoding="utf-8", newline="\n")
        writes.append(IntegrationWrite(path=path, status=status, tool=file.tool))
    return writes


def claude_skill_content() -> str:
    """Return the Claude Code skill that delegates work to Headmaster."""

    return dedent(
        """\
        ---
        description: >-
          Delegate work to the local Headmaster (해마) orchestration CLI. Use when
          the user says 해마, haema, headmaster, 헤드마스터, or asks Headmaster to
          coordinate a task.
        argument-hint: <task> [Headmaster flags]
        ---

        # Headmaster Delegation

        Use this skill to hand the user's task to Headmaster.

        ## Inputs

        - Treat `$ARGUMENTS` as the Headmaster task. If it is empty, use the user's
          latest request after the trigger word.
        - Default to `--provider fake` for dry runs.
        - If the user asks to use a real local OAuth CLI, choose `--provider claude`,
          `--provider codex`, or `--provider agy`.
        - Use `--approval grant` for unattended CLI delegation unless the user
          explicitly asks for manual approval.
        - Use `--orchestra b2b_website_v8` only when the user asks for full
          multi-agent orchestration.

        ## Procedure

        1. Locate the Headmaster backend directory. In this repository it is `backend`.
        2. Run Headmaster from that directory:

           ```powershell
           uv run headmaster run "<task>" --provider <provider> --approval grant
           ```

        3. If the user supplied extra Headmaster flags, preserve them.
        4. Report `task_id`, `final_state`, `artifact_path`, and `failure_reason` when present.
        5. If `uv`, `headmaster`, or the requested provider CLI is missing, report
           the exact missing command and the login/setup command to run.
        """
    )


def claude_command_content() -> str:
    """Return the legacy Claude Code command fallback."""

    return dedent(
        """\
        ---
        description: Delegate work to Headmaster (해마).
        argument-hint: <task> [Headmaster flags]
        ---

        Invoke the `haema` skill for this request, preserving these arguments:

        $ARGUMENTS

        If the skill is unavailable, run from the repository's `backend` directory:

        ```powershell
        uv run headmaster run "<task>" --provider fake --approval grant
        ```
        """
    )


def agent_skill_content() -> str:
    """Return a shared Agent Skills workflow for Codex and Antigravity."""

    return dedent(
        """\
        ---
        name: haema
        description: >-
          Delegate work to the local Headmaster (해마) orchestration CLI. Use when
          the user says 해마, haema, headmaster, 헤드마스터, or asks Headmaster to
          coordinate a task.
        argument-hint: <task> [Headmaster flags]
        ---

        # Headmaster Delegation

        Use this skill to hand the user's task to Headmaster.

        ## Inputs

        - Treat the invocation arguments as the Headmaster task. If they are empty,
          use the user's latest request after the trigger word.
        - Default to `--provider fake` for dry runs.
        - If the user asks to use a real local OAuth CLI, choose `--provider claude`,
          `--provider codex`, or `--provider agy`.
        - Use `--approval grant` for unattended CLI delegation unless the user
          explicitly asks for manual approval.
        - Use `--orchestra b2b_website_v8` only when the user asks for full
          multi-agent orchestration.

        ## Procedure

        1. Locate the Headmaster backend directory. In this repository it is `backend`.
        2. Run Headmaster from that directory:

           ```powershell
           uv run headmaster run "<task>" --provider <provider> --approval grant
           ```

        3. Preserve any explicit Headmaster flags from the user.
        4. Report `task_id`, `final_state`, `artifact_path`, and `failure_reason` when present.
        5. If `uv`, `headmaster`, or the requested provider CLI is missing, report
           the exact missing command and the login/setup command to run.
        """
    )


def codex_prompt_content() -> str:
    """Return a Codex custom prompt fallback for older slash workflows."""

    return dedent(
        """\
        ---
        description: Delegate work to Headmaster (해마)
        argument-hint: <task> [Headmaster flags]
        ---

        Delegate this request to the local Headmaster CLI.

        - Treat the prompt arguments as the task.
        - Run from the repository's `backend` directory:
          `uv run headmaster run "<task>" --provider fake --approval grant`
        - If I specify `--provider claude`, `--provider codex`, or `--provider agy`, preserve it.
        - Report `task_id`, `final_state`, `artifact_path`, and `failure_reason` when present.
        """
    )
