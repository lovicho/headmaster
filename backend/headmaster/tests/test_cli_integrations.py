"""CLI integration scaffolds for external agent CLIs."""

from pathlib import Path

import pytest

from headmaster.cli import main
from headmaster.integrations import (
    build_integration_files,
    parse_tools,
    write_integration_files,
)


def test_project_integration_files_include_agent_entrypoints(tmp_path: Path) -> None:
    files = build_integration_files(
        scope="project", root=tmp_path, tools=("claude", "codex", "agy")
    )
    relative_paths = {file.path.relative_to(tmp_path).as_posix() for file in files}

    assert ".claude/skills/haema/SKILL.md" in relative_paths
    assert ".claude/commands/haema.md" in relative_paths
    assert ".agents/skills/haema/SKILL.md" in relative_paths
    assert ".agent/skills/haema/SKILL.md" in relative_paths
    assert ".codex/prompts/haema.md" not in relative_paths
    assert all("uv run headmaster run" in file.content for file in files)


def test_user_integration_includes_codex_prompt_fallback(tmp_path: Path) -> None:
    files = build_integration_files(
        scope="user",
        root=tmp_path / "repo",
        home=tmp_path / "home",
        tools=("codex", "agy"),
    )
    relative_paths = {file.path.relative_to(tmp_path / "home").as_posix() for file in files}

    assert ".agents/skills/haema/SKILL.md" in relative_paths
    assert ".codex/prompts/haema.md" in relative_paths
    assert ".agent/skills/haema/SKILL.md" in relative_paths
    assert ".gemini/antigravity/skills/haema/SKILL.md" in relative_paths


def test_write_integration_files_is_idempotent(tmp_path: Path) -> None:
    files = build_integration_files(scope="project", root=tmp_path, tools=("claude",))

    first = write_integration_files(files)
    second = write_integration_files(files)

    assert {write.status for write in first} == {"installed"}
    assert {write.status for write in second} == {"unchanged"}


def test_write_integration_files_does_not_clobber_without_force(tmp_path: Path) -> None:
    files = build_integration_files(scope="project", root=tmp_path, tools=("claude",))
    write_integration_files(files)
    files[0].path.write_text("local edit", encoding="utf-8")

    writes = write_integration_files(files, force=False)

    assert any(write.status == "skipped" for write in writes)
    assert files[0].path.read_text(encoding="utf-8") == "local edit"


def test_parse_tools_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unknown integration"):
        parse_tools("claude,nope")


def test_cli_integrations_command_installs_project_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["integrations", "--scope", "project", "--root", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / ".claude" / "skills" / "haema" / "SKILL.md").is_file()
    assert (tmp_path / ".agents" / "skills" / "haema" / "SKILL.md").is_file()
    assert (tmp_path / ".agent" / "skills" / "haema" / "SKILL.md").is_file()
    assert "installed:" in capsys.readouterr().out
