"""Task manager — runs orchestrator tasks in the background.

Task state is always derived from the event log (source of truth), so the
status endpoint stays correct mid-run and across process restarts.
"""

import asyncio

from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import OrchestraHarness
from headmaster.schemas.states import TERMINAL_STATES, TaskState, validate_transition
from headmaster.schemas.task_spec import TaskSpec
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_final_state

SOURCE = "headmaster.task_manager"


class TaskManager:
    def __init__(self, orchestrator: Orchestrator, store: EventStore) -> None:
        self._orchestrator = orchestrator
        self._store = store
        self._running: dict[str, asyncio.Task[OrchestratorResult]] = {}
        self._results: dict[str, OrchestratorResult] = {}

    def submit(
        self,
        spec: TaskSpec,
        *,
        harness_id: str | None = None,
        orchestra: OrchestraHarness | None = None,
    ) -> str:
        if (harness_id is None) == (orchestra is None):
            raise ValueError("exactly one of harness_id or orchestra must be given")
        if orchestra is not None:
            coroutine = self._orchestrator.run_orchestra(spec, orchestra)
        else:
            assert harness_id is not None
            coroutine = self._orchestrator.run_task(spec, harness_id)
        task = asyncio.get_running_loop().create_task(coroutine)
        self._running[spec.task_id] = task
        task.add_done_callback(lambda done: self._finish(spec.task_id, done))
        return spec.task_id

    def _finish(self, task_id: str, task: asyncio.Task[OrchestratorResult]) -> None:
        self._running.pop(task_id, None)
        if task.cancelled():
            self._record_failure(task_id, "background_task_cancelled")
            return
        exception = task.exception()
        if exception is not None:
            self._record_failure(
                task_id,
                "background_task_exception",
                error_type=type(exception).__name__,
                error=str(exception),
            )
            return
        self._results[task_id] = task.result()

    def _record_failure(self, task_id: str, reason: str, **extra: object) -> None:
        state = self.state_of(task_id)
        if state is None or state in TERMINAL_STATES:
            return
        validate_transition(state, TaskState.FAILED)
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.STATE_CHANGED,
                subject=task_id,
                data={"from": state.value, "to": TaskState.FAILED.value},
            )
        )
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.TASK_FAILED,
                subject=task_id,
                data={"reason": reason, **extra},
            )
        )

    def known(self, task_id: str) -> bool:
        return bool(self._store.for_task(task_id)) or task_id in self._running

    def is_running(self, task_id: str) -> bool:
        return task_id in self._running

    def state_of(self, task_id: str) -> TaskState | None:
        events = self._store.for_task(task_id)
        if not events:
            return None
        return replay_final_state(events)

    def result_of(self, task_id: str) -> OrchestratorResult | None:
        return self._results.get(task_id)

    def task_ids(self) -> list[str]:
        return sorted(set(self._store.task_ids()) | set(self._running))
