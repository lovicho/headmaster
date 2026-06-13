"""Restart-safe approval recovery for the control API."""

from collections.abc import Callable, Mapping
from pathlib import Path

from headmaster.api.projection import ProjectionError, TaskEventProjector, as_str
from headmaster.schemas.approval import ApprovalDecision, ApprovalTicket
from headmaster.schemas.artifact import Artifact, content_sha256
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness
from headmaster.schemas.states import TaskState, validate_transition
from headmaster.storage.event_store import EventStore

SOURCE = "headmaster.api.recovery"


class RecoveryError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ApprovalRecoveryService:
    def __init__(
        self,
        *,
        store: EventStore,
        projector: TaskEventProjector,
        registry: Mapping[str, AgentHarness],
        state_of: Callable[[str], TaskState | None],
        artifact_dir: Path | None,
    ) -> None:
        self._store = store
        self._projector = projector
        self._registry = registry
        self._state_of = state_of
        self._artifact_dir = artifact_dir

    def _append_state_change(
        self, task_id: str, current: TaskState, target: TaskState
    ) -> TaskState:
        validate_transition(current, target)
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.STATE_CHANGED,
                subject=task_id,
                data={"from": current.value, "to": target.value},
            )
        )
        return target

    def recover_denied_approval(
        self, ticket: ApprovalTicket, decision: ApprovalDecision
    ) -> None:
        state = self._state_of(ticket.task_id)
        if state is None:
            raise RecoveryError(404, f"unknown task '{ticket.task_id}'")
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.APPROVAL_DENIED,
                subject=ticket.task_id,
                data={"ticket_id": ticket.ticket_id, **decision.model_dump(mode="json")},
            )
        )
        if state is not TaskState.FAILED:
            self._append_state_change(ticket.task_id, state, TaskState.FAILED)
            self._store.append(
                Event(
                    source=SOURCE,
                    type=EventType.TASK_FAILED,
                    subject=ticket.task_id,
                    data={
                        "reason": "approval_denied",
                        "ticket_id": ticket.ticket_id,
                        "recovered_after_restart": True,
                    },
                )
            )

    def recover_granted_approval(
        self, ticket: ApprovalTicket, decision: ApprovalDecision
    ) -> None:
        if ticket.kind == "publish":
            self.recover_granted_publish(ticket, decision)
            return
        if ticket.kind == "budget_overrun":
            raise RecoveryError(
                409,
                "budget approvals cannot be granted after restart because the live "
                "budget ledger is not replayable yet; deny this ticket or rerun the task",
            )
        if ticket.kind == "phase_gate":
            raise RecoveryError(
                409,
                "phase gates cannot be granted after restart until phase draft snapshots "
                "are recorded; deny this ticket or rerun the task",
            )
        raise RecoveryError(409, f"unsupported approval kind '{ticket.kind}'")

    def recover_granted_publish(
        self, ticket: ApprovalTicket, decision: ApprovalDecision
    ) -> None:
        events = self._projector.events_for_task(ticket.task_id)
        state = self._state_of(ticket.task_id)
        if state is None:
            raise RecoveryError(404, f"unknown task '{ticket.task_id}'")
        if state is not TaskState.AWAITING_HUMAN_APPROVAL:
            raise RecoveryError(409, f"task is not awaiting approval (state={state.value})")

        try:
            spec = self._projector.task_spec_from_snapshot(ticket.task_id)
            produced_by = self._projector.harness_id_from_snapshot(ticket.task_id)
            content = self._projector.draft_content_before_approval(
                events, ticket=ticket, produced_by=produced_by
            )
            evidence_bundle_id = self._projector.bundle_id_before_approval(
                events, ticket=ticket, produced_by=produced_by
            )
        except ProjectionError as exc:
            raise RecoveryError(exc.status_code, exc.message) from exc

        harness = self._registry.get(produced_by)
        if harness is None:
            raise RecoveryError(409, f"unknown recovered harness '{produced_by}'")

        artifact = Artifact(
            task_id=spec.task_id,
            produced_by=produced_by,
            format=harness.output_contract.format,
            content=content,
            content_hash=content_sha256(content),
            evidence_bundle_id=evidence_bundle_id,
            critique_id=as_str(ticket.details.get("critique_id")),
        )
        artifact_path: str | None = None
        if self._artifact_dir is not None:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            path = self._artifact_dir / f"{spec.task_id}.md"
            path.write_text(artifact.content, encoding="utf-8")
            artifact_path = str(path)

        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.APPROVAL_GRANTED,
                subject=ticket.task_id,
                data={"ticket_id": ticket.ticket_id, **decision.model_dump(mode="json")},
            )
        )
        state = self._append_state_change(ticket.task_id, state, TaskState.VALIDATED)
        state = self._append_state_change(ticket.task_id, state, TaskState.PUBLISHING)
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.ARTIFACT_PUBLISHED,
                subject=ticket.task_id,
                data={
                    "artifact_id": artifact.artifact_id,
                    "content_hash": artifact.content_hash,
                    "format": artifact.format,
                    "produced_by": artifact.produced_by,
                    "evidence_bundle_id": artifact.evidence_bundle_id,
                    "critique_id": artifact.critique_id,
                    "content": artifact.content,
                    "path": artifact_path,
                    "recovered_after_restart": True,
                },
            )
        )
        state = self._append_state_change(ticket.task_id, state, TaskState.ASSIMILATING)
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.KNOWLEDGE_ASSIMILATED,
                subject=ticket.task_id,
                data={
                    "records": [],
                    "reused_assets": [],
                    "promoted": [],
                    "quarantined": False,
                    "recovered_after_restart": True,
                },
            )
        )
        self._append_state_change(ticket.task_id, state, TaskState.COMPLETED)
        self._store.append(
            Event(
                source=SOURCE,
                type=EventType.TASK_COMPLETED,
                subject=ticket.task_id,
                data={"recovered_after_restart": True},
            )
        )
