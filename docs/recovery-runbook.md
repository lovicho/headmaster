# Headmaster Recovery Runbook

Headmaster treats the event log as the source of truth. Restart recovery must
therefore fold existing events and avoid re-calling models unless a future
workflow explicitly records enough replay inputs to do so safely.

## What Recovers Automatically

- Completed tasks remain visible through `GET /v1/tasks/{task_id}` after the API
  process restarts.
- Published artifact metadata and content are returned through
  `GET /v1/tasks/{task_id}/artifact` when the artifact was stored in the
  `artifact.published` event or can still be read from the recorded path.
- Pending approval tickets are rebuilt from `approval.requested` events, minus
  tickets that already have `approval.granted` or `approval.denied`.
- A pending final `publish` approval can be granted after restart. The recovery
  service rebuilds the artifact from the recorded model response and bundle
  events, emits the publish and assimilation events, then completes the task.
- Any pending approval can be denied after restart. Denial closes the task as
  `failed` and records an audit event.

## Current Safety Boundaries

`budget_overrun` and intermediate `phase_gate` approvals are not granted after a
restart yet. They pause inside a live orchestrator coroutine with in-memory
execution context:

- `budget_overrun` depends on the live budget ledger and the next execution loop.
- intermediate `phase_gate` depends on phase-local approved draft snapshots and
  pending phase order.

After restart, granting either ticket returns HTTP `409 Conflict`. Denial is
safe and remains supported.

## Operator Checks

List pending approvals:

```powershell
curl http://127.0.0.1:8400/v1/approvals
```

Grant a recoverable final publish approval:

```powershell
curl -X POST http://127.0.0.1:8400/v1/approvals/<ticket_id> `
  -H "Content-Type: application/json" `
  -d '{"granted": true, "approver": "operator"}'
```

Deny any pending approval:

```powershell
curl -X POST http://127.0.0.1:8400/v1/approvals/<ticket_id> `
  -H "Content-Type: application/json" `
  -d '{"granted": false, "approver": "operator", "note": "restart boundary"}'
```

Verify replayed task state:

```powershell
uv run headmaster replay <task_id> --store ./data/events.sqlite3
curl http://127.0.0.1:8400/v1/tasks/<task_id>
curl http://127.0.0.1:8400/v1/tasks/<task_id>/artifact
```

## Implementation Map

- `headmaster.api.projection.TaskEventProjector` folds event logs into API views.
- `headmaster.api.recovery.ApprovalRecoveryService` applies restart-safe
  approval decisions.
- `headmaster.api.main` owns HTTP routing and converts projection/recovery
  errors to API responses.
- `headmaster.api.task_manager.TaskManager` records background task failures so
  in-flight tasks do not remain stuck after exceptions.

## Future Resume Work

To grant `budget_overrun` after restart, persist a resumable execution checkpoint
before awaiting approval. The checkpoint needs the task spec, selected topology,
ledger status, current revision notes, recovery counters, supplied asset ids,
and the next orchestrator step.

To grant `phase_gate` after restart, persist phase snapshots before each human
gate. The snapshot needs the phase id, gate id, approved drafts, bundle ids,
critique ids, accumulated sections, reused asset ids, and the next phase index.

Both extensions should add events before `approval.requested`, then route the
grant path through `ApprovalRecoveryService` instead of reconstructing from
partial model events.
