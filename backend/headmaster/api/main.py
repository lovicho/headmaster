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
from pydantic import BaseModel, Field

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
    AnthropicAdapter,
    FakeAdapter,
    ModelAdapter,
    ModelGateway,
    OpenAIAdapter,
    load_routing,
)
from headmaster.execution_plane.orchestrator import Orchestrator
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
        "fake": FakeAdapter(),
    }
    budget_config = load_budget_config()
    approvals = QueueApprovalGateway()
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(
            ModelGateway(load_routing(), adapters, provider_override=provider)
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

    app = FastAPI(title="Headmaster Control API", version="0.1.0")

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
        state = manager.state_of(task_id)
        if state is None:
            raise HTTPException(404, f"unknown task '{task_id}'")
        result = manager.result_of(task_id)
        return TaskStatus(
            task_id=task_id,
            state=state.value,
            running=manager.is_running(task_id),
            failure_reason=result.failure_reason if result else None,
            artifact_id=result.artifact.artifact_id if result and result.artifact else None,
            artifact_path=result.artifact_path if result else None,
            supplied_asset_ids=result.supplied_asset_ids if result else [],
            reused_asset_ids=result.reused_asset_ids if result else [],
            critiques=[
                CritiqueSummary(
                    target_agent=critique.target_agent,
                    status=critique.status.value,
                    zero_shot_detected=critique.zero_shot_detected,
                )
                for critique in (result.critiques if result else [])
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
        result = manager.result_of(task_id)
        if result is None or result.artifact is None:
            raise HTTPException(404, f"no published artifact for task '{task_id}'")
        artifact = result.artifact
        return ArtifactResponse(
            artifact_id=artifact.artifact_id,
            content_hash=artifact.content_hash,
            format=artifact.format,
            content=artifact.content,
        )

    @app.get("/v1/approvals", response_model=list[ApprovalTicket])
    async def pending_approvals() -> list[ApprovalTicket]:
        return approvals.pending()

    @app.post("/v1/approvals/{ticket_id}")
    async def resolve_approval(
        ticket_id: str, request: ResolveApprovalRequest
    ) -> dict[str, bool]:
        resolved = approvals.resolve(
            ticket_id,
            ApprovalDecision(
                granted=request.granted, approver=request.approver, note=request.note
            ),
        )
        if not resolved:
            raise HTTPException(404, f"unknown or already-resolved ticket '{ticket_id}'")
        return {"resolved": True, "granted": request.granted}

    @app.get("/v1/metrics", response_model=Metrics)
    async def metrics() -> Metrics:
        return compute_metrics(store, pricing=budget_config.pricing)

    @app.post("/v1/evals/run", response_model=EvalReport)
    async def run_evals() -> EvalReport:
        return run_golden_suite(_DEFAULT_GOLDEN, registry)

    return app
