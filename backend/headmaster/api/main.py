"""FastAPI control API.

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
from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from headmaster.api.projection import ProjectionError, TaskEventProjector
from headmaster.api.recovery import ApprovalRecoveryService, RecoveryError
from headmaster.api.task_manager import TaskManager
from headmaster.assurance_plane.approval_gateway import QueueApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.assurance_plane.evaluator import EvalReport, run_golden_suite
from headmaster.assurance_plane.metrics import Metrics, compute_metrics
from headmaster.control_plane.budget_ledger import load_budget_config
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.memory import KnowledgeManager, MemoryFabric
from headmaster.execution_plane.models import (
    AgyCliAdapter,
    AnthropicAdapter,
    ClaudeCodeCliAdapter,
    CodexCliAdapter,
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
from headmaster.schemas.harness_manifest import AgentHarness, OrchestraHarness
from headmaster.schemas.task_spec import Budget
from headmaster.storage.event_store import EventStore

_DEFAULT_GOLDEN = (
    Path(__file__).resolve().parent.parent / "tests" / "golden" / "critic_golden.json"
)


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
    rejection_codes: list[str] = Field(default_factory=list)
    rejection_categories: list[str] = Field(default_factory=list)


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


def _raise_api_error(exc: ProjectionError | RecoveryError) -> NoReturn:
    raise HTTPException(exc.status_code, exc.message)


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
        "claude": ClaudeCodeCliAdapter(),
        "codex": CodexCliAdapter(),
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
    projector = TaskEventProjector(store)
    recovery = ApprovalRecoveryService(
        store=store,
        projector=projector,
        registry=registry,
        state_of=manager.state_of,
        artifact_dir=artifact_dir,
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
        try:
            projection = projector.task_status(
                task_id=task_id,
                state=manager.state_of(task_id),
                running=manager.is_running(task_id),
                result=manager.result_of(task_id),
            )
        except ProjectionError as exc:
            _raise_api_error(exc)
        return TaskStatus(
            task_id=projection.task_id,
            state=projection.state.value,
            running=projection.running,
            failure_reason=projection.failure_reason,
            artifact_id=projection.artifact_id,
            artifact_path=projection.artifact_path,
            supplied_asset_ids=projection.supplied_asset_ids,
            reused_asset_ids=projection.reused_asset_ids,
            critiques=[
                CritiqueSummary(
                    target_agent=critique.target_agent,
                    status=critique.status.value,
                    zero_shot_detected=critique.zero_shot_detected,
                    rejection_codes=[
                        finding.code.value
                        for finding in critique.findings
                        if finding.code is not None
                    ],
                    rejection_categories=sorted(
                        {
                            finding.category.value
                            for finding in critique.findings
                            if finding.category is not None
                        }
                    ),
                )
                for critique in projection.critiques
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
        try:
            artifact = projector.artifact(task_id, manager.result_of(task_id))
        except ProjectionError as exc:
            _raise_api_error(exc)
        return ArtifactResponse(
            artifact_id=artifact.artifact_id,
            content_hash=artifact.content_hash,
            format=artifact.format,
            content=artifact.content,
        )

    @app.get("/v1/approvals", response_model=list[ApprovalTicket])
    async def pending_approvals() -> list[ApprovalTicket]:
        return projector.pending_approvals(approvals.pending())

    @app.post("/v1/approvals/{ticket_id}")
    async def resolve_approval(
        ticket_id: str, request: ResolveApprovalRequest
    ) -> dict[str, bool]:
        decision = ApprovalDecision(
            granted=request.granted, approver=request.approver, note=request.note
        )
        resolved = approvals.resolve(ticket_id, decision)
        if not resolved:
            ticket = projector.pending_approvals_from_events().get(ticket_id)
            if ticket is None:
                raise HTTPException(
                    404, f"unknown or already-resolved ticket '{ticket_id}'"
                )
            try:
                if request.granted:
                    recovery.recover_granted_approval(ticket, decision)
                else:
                    recovery.recover_denied_approval(ticket, decision)
            except RecoveryError as exc:
                _raise_api_error(exc)
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
