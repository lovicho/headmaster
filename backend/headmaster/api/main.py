"""FastAPI control API (subset of the 2nd report's API spec).

    POST /v1/tasks                  submit a task (single-agent or orchestra)
    GET  /v1/tasks                  list known tasks
    GET  /v1/tasks/{id}             status (state replayed from the event log)
    GET  /v1/tasks/{id}/events      full trace
    GET  /v1/tasks/{id}/artifact    published artifact content
    GET  /v1/approvals              pending human-approval tickets
    POST /v1/approvals/{ticket_id}  resolve a pending ticket
    GET  /v1/metrics                operational metrics
    POST /v1/evals/run              golden-set regression suite
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from headmaster.api.task_manager import TaskManager
from headmaster.assurance_plane.approval_gateway import QueueApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.assurance_plane.evaluator import EvalReport, run_golden_suite
from headmaster.assurance_plane.metrics import Metrics, compute_metrics
from headmaster.control_plane.budget_ledger import load_budget_config
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime, extract_json_object
from headmaster.execution_plane.memory import KnowledgeManager, MemoryFabric
from headmaster.execution_plane.models import (
    AgyCliAdapter,
    AnthropicAdapter,
    FakeAdapter,
    GeminiCliAdapter,
    ModelAdapter,
    ModelGateway,
    OpenAIAdapter,
    load_routing,
)
from headmaster.execution_plane.orchestrator import Orchestrator
from headmaster.execution_plane.tools import build_default_tool_gateway
from headmaster.schemas.approval import ApprovalDecision, ApprovalTicket
from headmaster.schemas.artifact import Artifact, content_sha256
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import AgentHarness, OrchestraHarness
from headmaster.schemas.states import TaskState, validate_transition
from headmaster.schemas.task_spec import Budget, TaskSpec
from headmaster.storage.event_store import EventStore

_DEFAULT_GOLDEN = (
    Path(__file__).resolve().parent.parent / "tests" / "golden" / "critic_golden.json"
)
_RECOVERY_SOURCE = "headmaster.api.recovery"


class CreateTaskRequest(BaseModel):
    text: str
    harness: str | None = None
    orchestra: str | None = None
    needs_human_approval: bool = False
    max_tokens: int | None = None
    max_model_cost_usd: float | None = None


class CreateTaskResponse(BaseModel):
    task_id: str
    state: str


class CritiqueSummary(BaseModel):
    target_agent: str
    status: str
    zero_shot_detected: bool


class TaskStatus(BaseModel):
    task_id: str
    state: str
    running: bool
    failure_reason: str | None = None
    artifact_id: str | None = None
    artifact_path: str | None = None
    supplied_asset_ids: list[str] = Field(default_factory=list)
    reused_asset_ids: list[str] = Field(default_factory=list)
    critiques: list[CritiqueSummary] = Field(default_factory=list)


class ArtifactResponse(BaseModel):
    artifact_id: str
    content_hash: str
    format: str
    content: str


class ResolveApprovalRequest(BaseModel):
    granted: bool
    approver: str = "api"
    note: str | None = None


def create_app(
    *,
    store: EventStore,
    fabric: MemoryFabric,
    provider: str | None = None,
    artifact_dir: Path | None = None,
    static_dir: Path | None = None,
    max_revisions: int = 2,
) -> FastAPI:
    all_harnesses = load_all()
    registry = {
        harness_id: harness
        for harness_id, harness in all_harnesses.items()
        if isinstance(harness, AgentHarness)
    }
    orchestras = {
        harness_id: harness
        for harness_id, harness in all_harnesses.items()
        if isinstance(harness, OrchestraHarness)
    }
    adapters: dict[str, ModelAdapter] = {
        "anthropic": AnthropicAdapter(),
        "openai": OpenAIAdapter(),
        "agy": AgyCliAdapter(),
        "gemini": GeminiCliAdapter(),
        "fake": FakeAdapter(),
    }
    budget_config = load_budget_config()
    approvals = QueueApprovalGateway()
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(
            ModelGateway(load_routing(), adapters, provider_override=provider),
            tool_gateway=build_default_tool_gateway(fabric),
        ),
        critic=CriticService(),
        registry=registry,
        knowledge_manager=KnowledgeManager(fabric),
        approval_gateway=approvals,
        pricing=budget_config.pricing,
        soft_ratio=budget_config.soft_ratio,
        max_revisions=max_revisions,
        artifact_dir=artifact_dir,
    )
    manager = TaskManager(orchestrator, store)

    def _as_str(value: object) -> str | None:
        return value if isinstance(value, str) else None

    def _str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    def _last_event_data(
        events: list[Event], event_type: EventType
    ) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.type is event_type:
                return event.data
        return None

    def _published_artifact_data(events: list[Event]) -> dict[str, Any] | None:
        return _last_event_data(events, EventType.ARTIFACT_PUBLISHED)

    def _critiques_from_events(events: list[Event]) -> list[CritiqueReport]:
        return [
            CritiqueReport.model_validate(event.data)
            for event in events
            if event.type is EventType.CRITIQUE_ISSUED
        ]

    def _pending_approvals_from_events() -> dict[str, ApprovalTicket]:
        pending: dict[str, ApprovalTicket] = {}
        for event in store.all_events():
            if event.type is EventType.APPROVAL_REQUESTED:
                ticket = ApprovalTicket.model_validate(event.data)
                pending[ticket.ticket_id] = ticket
            elif event.type in {EventType.APPROVAL_GRANTED, EventType.APPROVAL_DENIED}:
                ticket_id = _as_str(event.data.get("ticket_id"))
                if ticket_id is not None:
                    pending.pop(ticket_id, None)
        return pending

    def _pending_approvals() -> list[ApprovalTicket]:
        pending = _pending_approvals_from_events()
        for ticket in approvals.pending():
            pending[ticket.ticket_id] = ticket
        return sorted(pending.values(), key=lambda ticket: ticket.ticket_id)

    def _task_spec_from_events(events: list[Event]) -> TaskSpec:
        registered = next(
            (event for event in events if event.type is EventType.TASK_REGISTERED), None
        )
        raw_spec = registered.data.get("spec") if registered else None
        if not isinstance(raw_spec, dict):
            raise HTTPException(409, "task spec is unavailable in the event log")
        return TaskSpec.model_validate(raw_spec)

    def _harness_id_from_events(events: list[Event]) -> str:
        classified = next(
            (event for event in events if event.type is EventType.TASK_CLASSIFIED), None
        )
        harness_id = _as_str(classified.data.get("harness_id")) if classified else None
        if harness_id is None:
            raise HTTPException(409, "task cannot be resumed without an agent harness id")
        return harness_id

    def _event_index(events: list[Event], ticket_id: str) -> int:
        for index, event in enumerate(events):
            if (
                event.type is EventType.APPROVAL_REQUESTED
                and event.data.get("ticket_id") == ticket_id
            ):
                return index
        raise HTTPException(404, f"unknown approval ticket '{ticket_id}'")

    def _draft_content_before_approval(
        events: list[Event], *, ticket: ApprovalTicket, produced_by: str
    ) -> str:
        approval_index = _event_index(events, ticket.ticket_id)
        for event in reversed(events[:approval_index]):
            if event.type is not EventType.MODEL_RESPONDED:
                continue
            if event.data.get("agent") != produced_by:
                continue
            text = _as_str(event.data.get("text")) or ""
            parsed = extract_json_object(text)
            raw_content = parsed.get("content") if parsed is not None else None
            if isinstance(raw_content, str) and raw_content.strip():
                return raw_content
            if text.strip():
                return text
        raise HTTPException(409, "approved draft content is unavailable in the event log")

    def _bundle_id_before_approval(
        events: list[Event], *, ticket: ApprovalTicket, produced_by: str
    ) -> str:
        approval_index = _event_index(events, ticket.ticket_id)
        for event in reversed(events[:approval_index]):
            if event.type is not EventType.ARTIFACT_PRODUCED:
                continue
            if event.data.get("agent") != produced_by:
                continue
            bundle_id = _as_str(event.data.get("bundle_id"))
            if bundle_id is not None:
                return bundle_id
        return "recovered_unknown_bundle"

    def _append_state_change(
        task_id: str, current: TaskState, target: TaskState
    ) -> TaskState:
        validate_transition(current, target)
        store.append(
            Event(
                source=_RECOVERY_SOURCE,
                type=EventType.STATE_CHANGED,
                subject=task_id,
                data={"from": current.value, "to": target.value},
            )
        )
        return target

    def _artifact_response_from_events(task_id: str) -> ArtifactResponse:
        result = manager.result_of(task_id)
        if result is not None and result.artifact is not None:
            artifact = result.artifact
            return ArtifactResponse(
                artifact_id=artifact.artifact_id,
                content_hash=artifact.content_hash,
                format=artifact.format,
                content=artifact.content,
            )

        events = store.for_task(task_id)
        if not events:
            raise HTTPException(404, f"unknown task '{task_id}'")
        artifact_data = _published_artifact_data(events)
        if artifact_data is None:
            raise HTTPException(404, f"no published artifact for task '{task_id}'")

        artifact_id = _as_str(artifact_data.get("artifact_id"))
        content = _as_str(artifact_data.get("content"))
        path = _as_str(artifact_data.get("path"))
        if content is None and path is not None:
            artifact_file = Path(path)
            if artifact_file.is_file():
                content = artifact_file.read_text(encoding="utf-8")
        if artifact_id is None or content is None:
            raise HTTPException(
                404, f"published artifact content is unavailable for task '{task_id}'"
            )
        return ArtifactResponse(
            artifact_id=artifact_id,
            content_hash=_as_str(artifact_data.get("content_hash"))
            or content_sha256(content),
            format=_as_str(artifact_data.get("format")) or "markdown",
            content=content,
        )

    def _recover_denied_approval(
        ticket: ApprovalTicket, decision: ApprovalDecision
    ) -> None:
        state = manager.state_of(ticket.task_id)
        if state is None:
            raise HTTPException(404, f"unknown task '{ticket.task_id}'")
        store.append(
            Event(
                source=_RECOVERY_SOURCE,
                type=EventType.APPROVAL_DENIED,
                subject=ticket.task_id,
                data={"ticket_id": ticket.ticket_id, **decision.model_dump(mode="json")},
            )
        )
        if state is not TaskState.FAILED:
            _append_state_change(ticket.task_id, state, TaskState.FAILED)
            store.append(
                Event(
                    source=_RECOVERY_SOURCE,
                    type=EventType.TASK_FAILED,
                    subject=ticket.task_id,
                    data={
                        "reason": "approval_denied",
                        "ticket_id": ticket.ticket_id,
                        "recovered_after_restart": True,
                    },
                )
            )

    def _recover_granted_publish(
        ticket: ApprovalTicket, decision: ApprovalDecision
    ) -> None:
        if ticket.kind != "publish":
            raise HTTPException(
                409,
                "only final publish approvals can be recovered after restart; "
                "deny this ticket or rerun the task",
            )
        events = store.for_task(ticket.task_id)
        state = manager.state_of(ticket.task_id)
        if state is None:
            raise HTTPException(404, f"unknown task '{ticket.task_id}'")
        if state is not TaskState.AWAITING_HUMAN_APPROVAL:
            raise HTTPException(409, f"task is not awaiting approval (state={state.value})")

        spec = _task_spec_from_events(events)
        produced_by = _harness_id_from_events(events)
        harness = registry.get(produced_by)
        if harness is None:
            raise HTTPException(409, f"unknown recovered harness '{produced_by}'")

        critique_id = _as_str(ticket.details.get("critique_id"))
        content = _draft_content_before_approval(
            events, ticket=ticket, produced_by=produced_by
        )
        artifact = Artifact(
            task_id=spec.task_id,
            produced_by=produced_by,
            format=harness.output_contract.format,
            content=content,
            content_hash=content_sha256(content),
            evidence_bundle_id=_bundle_id_before_approval(
                events, ticket=ticket, produced_by=produced_by
            ),
            critique_id=critique_id,
        )
        artifact_path: str | None = None
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            path = artifact_dir / f"{spec.task_id}.md"
            path.write_text(artifact.content, encoding="utf-8")
            artifact_path = str(path)

        store.append(
            Event(
                source=_RECOVERY_SOURCE,
                type=EventType.APPROVAL_GRANTED,
                subject=ticket.task_id,
                data={"ticket_id": ticket.ticket_id, **decision.model_dump(mode="json")},
            )
        )
        state = _append_state_change(ticket.task_id, state, TaskState.VALIDATED)
        state = _append_state_change(ticket.task_id, state, TaskState.PUBLISHING)
        store.append(
            Event(
                source=_RECOVERY_SOURCE,
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
        state = _append_state_change(ticket.task_id, state, TaskState.ASSIMILATING)
        store.append(
            Event(
                source=_RECOVERY_SOURCE,
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
        state = _append_state_change(ticket.task_id, state, TaskState.COMPLETED)
        store.append(
            Event(
                source=_RECOVERY_SOURCE,
                type=EventType.TASK_COMPLETED,
                subject=ticket.task_id,
                data={"recovered_after_restart": True},
            )
        )

    app = FastAPI(title="Headmaster Control API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/v1/tasks", response_model=CreateTaskResponse)
    async def create_task(request: CreateTaskRequest) -> CreateTaskResponse:
        spec = compile_task(request.text, needs_human_approval=request.needs_human_approval)
        if request.max_tokens is not None or request.max_model_cost_usd is not None:
            spec.constraints.budget = Budget(
                max_tokens=request.max_tokens,
                max_model_cost_usd=request.max_model_cost_usd,
            )
        if request.orchestra is not None:
            orchestra = orchestras.get(request.orchestra)
            if orchestra is None:
                raise HTTPException(404, f"unknown orchestra '{request.orchestra}'")
            task_id = manager.submit(spec, orchestra=orchestra)
        else:
            harness_id = request.harness or "content"
            if harness_id not in registry:
                raise HTTPException(404, f"unknown harness '{harness_id}'")
            task_id = manager.submit(spec, harness_id=harness_id)
        return CreateTaskResponse(task_id=task_id, state="registered")

    @app.get("/v1/tasks", response_model=list[TaskStatus])
    async def list_tasks() -> list[TaskStatus]:
        return [_status(task_id) for task_id in manager.task_ids()]

    def _status(task_id: str) -> TaskStatus:
        events = store.for_task(task_id)
        state = manager.state_of(task_id)
        if state is None:
            raise HTTPException(404, f"unknown task '{task_id}'")
        result = manager.result_of(task_id)
        artifact_data = _published_artifact_data(events)
        failed_data = _last_event_data(events, EventType.TASK_FAILED)
        supplied_data = _last_event_data(events, EventType.KNOWLEDGE_SUPPLIED)
        assimilated_data = _last_event_data(events, EventType.KNOWLEDGE_ASSIMILATED)
        artifact_id = (
            result.artifact.artifact_id
            if result is not None and result.artifact is not None
            else _as_str(artifact_data.get("artifact_id")) if artifact_data else None
        )
        artifact_path = (
            result.artifact_path
            if result is not None
            else _as_str(artifact_data.get("path")) if artifact_data else None
        )
        supplied_asset_ids = (
            result.supplied_asset_ids
            if result is not None
            else _str_list(supplied_data.get("asset_ids")) if supplied_data else []
        )
        reused_asset_ids = (
            result.reused_asset_ids
            if result is not None
            else _str_list(assimilated_data.get("reused_assets"))
            if assimilated_data
            else []
        )
        failure_reason = (
            result.failure_reason
            if result is not None
            else _as_str(failed_data.get("reason")) if failed_data else None
        )
        critiques = result.critiques if result is not None else _critiques_from_events(events)
        return TaskStatus(
            task_id=task_id,
            state=state.value,
            running=manager.is_running(task_id),
            failure_reason=failure_reason,
            artifact_id=artifact_id,
            artifact_path=artifact_path,
            supplied_asset_ids=supplied_asset_ids,
            reused_asset_ids=reused_asset_ids,
            critiques=[
                CritiqueSummary(
                    target_agent=critique.target_agent,
                    status=critique.status.value,
                    zero_shot_detected=critique.zero_shot_detected,
                )
                for critique in critiques
            ],
        )

    @app.get("/v1/tasks/{task_id}", response_model=TaskStatus)
    async def task_status(task_id: str) -> TaskStatus:
        return _status(task_id)

    @app.get("/v1/tasks/{task_id}/events")
    async def task_events(task_id: str) -> list[dict[str, Any]]:
        events = store.for_task(task_id)
        if not events:
            raise HTTPException(404, f"unknown task '{task_id}'")
        return [event.model_dump(mode="json") for event in events]

    @app.get("/v1/tasks/{task_id}/artifact", response_model=ArtifactResponse)
    async def task_artifact(task_id: str) -> ArtifactResponse:
        return _artifact_response_from_events(task_id)

    @app.get("/v1/approvals", response_model=list[ApprovalTicket])
    async def pending_approvals() -> list[ApprovalTicket]:
        return _pending_approvals()

    @app.post("/v1/approvals/{ticket_id}")
    async def resolve_approval(
        ticket_id: str, request: ResolveApprovalRequest
    ) -> dict[str, bool]:
        decision = ApprovalDecision(
            granted=request.granted, approver=request.approver, note=request.note
        )
        resolved = approvals.resolve(
            ticket_id,
            decision,
        )
        if not resolved:
            ticket = _pending_approvals_from_events().get(ticket_id)
            if ticket is None:
                raise HTTPException(
                    404, f"unknown or already-resolved ticket '{ticket_id}'"
                )
            if request.granted:
                _recover_granted_publish(ticket, decision)
            else:
                _recover_denied_approval(ticket, decision)
        return {"resolved": True, "granted": request.granted}

    @app.get("/v1/metrics", response_model=Metrics)
    async def metrics() -> Metrics:
        return compute_metrics(store, pricing=budget_config.pricing)

    @app.post("/v1/evals/run", response_model=EvalReport)
    async def run_evals() -> EvalReport:
        return run_golden_suite(_DEFAULT_GOLDEN, registry)

    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app
