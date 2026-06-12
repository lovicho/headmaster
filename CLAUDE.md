# Claude Code Instructions

## Headmaster Invocation

- When the user says `해마`, `haema`, `headmaster`, or `헤드마스터`, delegate the requested task to the local Headmaster CLI.
- Prefer the `/haema` skill when it is available.
- If the skill is unavailable, run Headmaster from `backend`:

  ```powershell
  uv run headmaster run "<task>" --provider fake --approval grant
  ```

- Preserve explicit flags such as `--provider claude`, `--provider codex`, `--provider agy`, `--harness`, `--orchestra`, and `--approval`.
- Use `--orchestra b2b_website_v8` only when the user asks for full multi-agent orchestration.
- After Headmaster finishes, report `task_id`, `final_state`, `artifact_path`, and any `failure_reason`.
