"""Event-log projections for the control API.

These helpers are intentionally read-only: they fold recorded events into API
views without re-calling models or mutating task state.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from headmaster.execution_plane.agent_runtime import extract_json_object
from headmaster.execution_plane.orchestrator import OrchestratorResult
from headmaster.schemas.approval import ApprovalTicket
from headmaster.schemas.artifact import content_sha256
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.states import TaskState
from headmaster.schemas.task_spec import TaskSpec
from headmaster.storage.event_store import EventStore
from pydantic import BaseModel, Field

class TaskSnapshotState(BaseModel):
    artifact_data: dict[str, Any] | None = None
    failed_data: dict[str, Any] | None = None
    supplied_data: dict[str, Any] | None = None
    assimilated_data: dict[str, Any] | None = None
    critiques: list[dict[str, Any]] = Field(default_factory=list)
    task_spec: dict[str, Any] | None = None
    harness_id: str | None = None



class ProjectionError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class TaskProjection:
    task_id: str
    state: TaskState
    running: bool
    failure_reason: str | None = None
    artifact_id: str | None = None
    artifact_path: str | None = None
    supplied_asset_ids: list[str] = field(default_factory=list)
    reused_asset_ids: list[str] = field(default_factory=list)
    critiques: list[CritiqueReport] = field(default_factory=list)


@dataclass(frozen=True)
class ArtifactProjection:
    artifact_id: str
    content_hash: str
    format: str
    content: str


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


class TaskEventProjector:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def _fold_events(self, state: TaskSnapshotState, events: list[Event]) -> TaskSnapshotState:
        for event in events:
            if event.type is EventType.TASK_REGISTERED and state.task_spec is None:
                state.task_spec = event.data.get("spec")
            elif event.type is EventType.TASK_CLASSIFIED and state.harness_id is None:
                state.harness_id = as_str(event.data.get("harness_id"))
            elif event.type is EventType.ARTIFACT_PUBLISHED:
                state.artifact_data = event.data
            elif event.type is EventType.TASK_FAILED:
                state.failed_data = event.data
            elif event.type is EventType.KNOWLEDGE_SUPPLIED:
                state.supplied_data = event.data
            elif event.type is EventType.KNOWLEDGE_ASSIMILATED:
                state.assimilated_data = event.data
            elif event.type is EventType.CRITIQUE_ISSUED:
                state.critiques.append(event.data)
        return state

    def _get_snapshot(self, task_id: str) -> TaskSnapshotState:
        record = self._store.load_snapshot(task_id)
        if record is None:
            last_seq = 0
            state = TaskSnapshotState()
        else:
            last_seq, data = record
            state = TaskSnapshotState.model_validate(data)

        # We need the events to fold
        delta_rows = self._store.for_task_since_with_seq(task_id, last_seq)
        if not delta_rows:
            if last_seq == 0:
                raise ProjectionError(404, f"unknown task '{task_id}'")
            return state

        delta_events = [row[1] for row in delta_rows]
        state = self._fold_events(state, delta_events)
        
        new_last_seq = delta_rows[-1][0]
        
        # Lazy snapshotting if there are many events
        if len(delta_rows) >= 50:
            self._store.save_snapshot(task_id, new_last_seq, state.model_dump(mode="json"))

        return state


    def events_for_task(self, task_id: str) -> list[Event]:
        events = self._store.for_task(task_id)
        if not events:
            raise ProjectionError(404, f"unknown task '{task_id}'")
        return events

    def last_event_data(
        self, events: list[Event], event_type: EventType
    ) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.type is event_type:
                return event.data
        return None

    def published_artifact_data(self, events: list[Event]) -> dict[str, Any] | None:
        return self.last_event_data(events, EventType.ARTIFACT_PUBLISHED)

    def critiques_from_events(self, events: list[Event]) -> list[CritiqueReport]:
        return [
            CritiqueReport.model_validate(event.data)
            for event in events
            if event.type is EventType.CRITIQUE_ISSUED
        ]

    def pending_approvals_from_events(self) -> dict[str, ApprovalTicket]:
        pending: dict[str, ApprovalTicket] = {}
        events = self._store.events_of_types([
            EventType.APPROVAL_REQUESTED.value,
            EventType.APPROVAL_GRANTED.value,
            EventType.APPROVAL_DENIED.value,
        ])
        for event in events:
            if event.type is EventType.APPROVAL_REQUESTED:
                ticket = ApprovalTicket.model_validate(event.data)
                pending[ticket.ticket_id] = ticket
            elif event.type in {EventType.APPROVAL_GRANTED, EventType.APPROVAL_DENIED}:
                ticket_id = as_str(event.data.get("ticket_id"))
                if ticket_id is not None:
                    pending.pop(ticket_id, None)
        return pending

    def pending_approvals(
        self, live_tickets: Iterable[ApprovalTicket]
    ) -> list[ApprovalTicket]:
        pending = self.pending_approvals_from_events()
        for ticket in live_tickets:
            pending[ticket.ticket_id] = ticket
        return sorted(pending.values(), key=lambda ticket: ticket.ticket_id)

    def task_spec_from_snapshot(self, task_id: str) -> TaskSpec:
        snapshot = self._get_snapshot(task_id)
        raw_spec = snapshot.task_spec
        if not isinstance(raw_spec, dict):
            raise ProjectionError(409, "task spec is unavailable in the event log")
        return TaskSpec.model_validate(raw_spec)

    def harness_id_from_snapshot(self, task_id: str) -> str:
        snapshot = self._get_snapshot(task_id)
        harness_id = snapshot.harness_id
        if harness_id is None:
            raise ProjectionError(
                409, "task cannot be resumed without an agent harness id"
            )
        return harness_id

    def event_index(self, events: list[Event], ticket_id: str) -> int:
        for index, event in enumerate(events):
            if (
                event.type is EventType.APPROVAL_REQUESTED
                and event.data.get("ticket_id") == ticket_id
            ):
                return index
        raise ProjectionError(404, f"unknown approval ticket '{ticket_id}'")

    def draft_content_before_approval(
        self, events: list[Event], *, ticket: ApprovalTicket, produced_by: str
    ) -> str:
        approval_index = self.event_index(events, ticket.ticket_id)
        for event in reversed(events[:approval_index]):
            if event.type is not EventType.MODEL_RESPONDED:
                continue
            if event.data.get("agent") != produced_by:
                continue
            text = as_str(event.data.get("text")) or ""
            parsed = extract_json_object(text)
            raw_content = parsed.get("content") if parsed is not None else None
            if isinstance(raw_content, str) and raw_content.strip():
                return raw_content
            if text.strip():
                return text
        raise ProjectionError(409, "approved draft content is unavailable in the event log")

    def bundle_id_before_approval(
        self, events: list[Event], *, ticket: ApprovalTicket, produced_by: str
    ) -> str:
        approval_index = self.event_index(events, ticket.ticket_id)
        for event in reversed(events[:approval_index]):
            if event.type is not EventType.ARTIFACT_PRODUCED:
                continue
            if event.data.get("agent") != produced_by:
                continue
            bundle_id = as_str(event.data.get("bundle_id"))
            if bundle_id is not None:
                return bundle_id
        return "recovered_unknown_bundle"

    def task_status(
        self,
        *,
        task_id: str,
        state: TaskState | None,
        running: bool,
        result: OrchestratorResult | None,
    ) -> TaskProjection:
        snapshot = self._get_snapshot(task_id)
        if state is None:
            raise ProjectionError(404, f"unknown task '{task_id}'")

        artifact_data = snapshot.artifact_data
        failed_data = snapshot.failed_data
        supplied_data = snapshot.supplied_data
        assimilated_data = snapshot.assimilated_data

        artifact_id: str | None = None
        if result is not None and result.artifact is not None:
            artifact_id = result.artifact.artifact_id
        elif artifact_data is not None:
            artifact_id = as_str(artifact_data.get("artifact_id"))

        artifact_path: str | None = None
        if result is not None:
            artifact_path = result.artifact_path
        elif artifact_data is not None:
            artifact_path = as_str(artifact_data.get("path"))

        supplied_asset_ids: list[str]
        if result is not None:
            supplied_asset_ids = result.supplied_asset_ids
        elif supplied_data is not None:
            supplied_asset_ids = str_list(supplied_data.get("asset_ids"))
        else:
            supplied_asset_ids = []

        reused_asset_ids: list[str]
        if result is not None:
            reused_asset_ids = result.reused_asset_ids
        elif assimilated_data is not None:
            reused_asset_ids = str_list(assimilated_data.get("reused_assets"))
        else:
            reused_asset_ids = []

        failure_reason: str | None = None
        if result is not None:
            failure_reason = result.failure_reason
        elif failed_data is not None:
            failure_reason = as_str(failed_data.get("reason"))

        critiques = result.critiques if result is not None else [CritiqueReport.model_validate(c) for c in snapshot.critiques]
        return TaskProjection(
            task_id=task_id,
            state=state,
            running=running,
            failure_reason=failure_reason,
            artifact_id=artifact_id,
            artifact_path=artifact_path,
            supplied_asset_ids=supplied_asset_ids,
            reused_asset_ids=reused_asset_ids,
            critiques=critiques,
        )

    def artifact(self, task_id: str, result: OrchestratorResult | None) -> ArtifactProjection:
        if result is not None and result.artifact is not None:
            artifact = result.artifact
            return ArtifactProjection(
                artifact_id=artifact.artifact_id,
                content_hash=artifact.content_hash,
                format=artifact.format,
                content=artifact.content,
            )

        snapshot = self._get_snapshot(task_id)
        artifact_data = snapshot.artifact_data
        if artifact_data is None:
            raise ProjectionError(404, f"no published artifact for task '{task_id}'")

        artifact_id = as_str(artifact_data.get("artifact_id"))
        content = as_str(artifact_data.get("content"))
        path = as_str(artifact_data.get("path"))
        if content is None and path is not None:
            artifact_file = Path(path)
            if artifact_file.is_file():
                content = artifact_file.read_text(encoding="utf-8")
        if artifact_id is None or content is None:
            raise ProjectionError(
                404, f"published artifact content is unavailable for task '{task_id}'"
            )
        return ArtifactProjection(
            artifact_id=artifact_id,
            content_hash=as_str(artifact_data.get("content_hash"))
            or content_sha256(content),
            format=as_str(artifact_data.get("format")) or "markdown",
            content=content,
        )
