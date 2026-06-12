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
