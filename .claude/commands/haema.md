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
