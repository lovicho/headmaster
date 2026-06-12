# CLI Agent Integrations

Headmaster can be invoked from Claude Code, Codex CLI, and Antigravity CLI as a delegated local workflow.

## Project-scoped setup

This repository includes:

- `CLAUDE.md`: natural-language trigger guidance for Claude Code
- `AGENTS.md`: natural-language trigger guidance for Codex and other agent CLIs
- `.claude/skills/haema/SKILL.md`: Claude Code `/haema` skill
- `.claude/commands/haema.md`: legacy Claude Code `/haema` command fallback
- `.agents/skills/haema/SKILL.md`: Agent Skills workflow for Codex
- `.agent/skills/haema/SKILL.md`: Agent Skills workflow for Antigravity CLI

Start the agent CLI from the repository root, then use either natural language or the skill command:

```text
해마로 "시장 조사 요약" 실행해줘
/haema 시장 조사 요약 --provider fake
/haema 기능 구현 계획 --provider codex
```

## User-scoped setup

To install the same integration into the current user's agent configuration:

```powershell
cd backend
uv run headmaster integrations --scope user --tools all
```

This writes user-level Claude skills, `.agents/skills/haema` for Codex, `.agent/skills/haema` and `.gemini/antigravity/skills/haema` for AGY-style Agent Skills, and a Codex custom prompt fallback at `.codex/prompts/haema.md`.

Codex custom prompts are kept only as a compatibility fallback. Skills are the preferred reusable workflow.

## Provider selection

By default, the skill uses the offline `fake` provider so it can run without network credentials.

Use the local OAuth providers explicitly when needed:

```text
/haema 리팩터링 계획 작성 --provider claude
/haema 테스트 전략 작성 --provider codex
/haema 랜딩 페이지 초안 --provider agy
```

Required logins:

```powershell
claude auth login
codex login
agy
```

The `agy` login flow is interactive and depends on the installed Antigravity CLI version.
