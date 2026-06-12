"""Phase 4a gates: control API end-to-end over ASGI (offline, fake provider)."""

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from headmaster.api.main import create_app
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.memory import MemoryFabric
from headmaster.schemas import ApprovalKind, ApprovalTicket, Event, EventType, TaskState
from headmaster.storage.event_store import EventStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(
    *,
    store: EventStore | None = None,
    fabric: MemoryFabric | None = None,
    artifact_dir: Path | None = None,
) -> FastAPI:
    return create_app(
        store=store or EventStore(),
        fabric=fabric or MemoryFabric(),
        provider="fake",
        artifact_dir=artifact_dir,
    )


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _wait_for_state(
    client: httpx.AsyncClient, task_id: str, *states: str, timeout: float = 5.0
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f"/v1/tasks/{task_id}")
        body: dict[str, object] = response.json()
        if response.status_code == 200 and body["state"] in states:
            return body
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"task {task_id} never reached {states}: {body}")
        await asyncio.sleep(0.02)


async def _wait_for_approval(
    client: httpx.AsyncClient, *, timeout: float = 5.0
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get("/v1/approvals")
        tickets: list[dict[str, object]] = response.json()
        if tickets:
            return tickets[0]
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("no approval ticket appeared")
        await asyncio.sleep(0.02)


@pytest.mark.anyio
async def test_task_lifecycle_over_api() -> None:
    async with _client(_app()) as client:
        created = await client.post("/v1/tasks", json={"text": "API demo task"})
        assert created.status_code == 200
        task_id = created.json()["task_id"]

        status = await _wait_for_state(client, task_id, "completed")
        assert status["running"] is False
        assert status["artifact_id"]

        events = await client.get(f"/v1/tasks/{task_id}/events")
        assert events.status_code == 200
        assert any(event["type"] == "task.completed" for event in events.json())

        artifact = await client.get(f"/v1/tasks/{task_id}/artifact")
        assert artifact.status_code == 200
        assert artifact.json()["content"]

        listing = await client.get("/v1/tasks")
        assert task_id in [item["task_id"] for item in listing.json()]

        metrics = await client.get("/v1/metrics")
        assert metrics.json()["completed"] == 1


@pytest.mark.anyio
async def test_http_approval_grant_flow() -> None:
    async with _client(_app()) as client:
        created = await client.post(
            "/v1/tasks", json={"text": "high risk task", "needs_human_approval": True}
        )
        task_id = created.json()["task_id"]

        ticket = await _wait_for_approval(client)
        assert ticket["kind"] == "publish"
        assert ticket["task_id"] == task_id

        resolved = await client.post(
            f"/v1/approvals/{ticket['ticket_id']}",
            json={"granted": True, "approver": "boss"},
        )
        assert resolved.status_code == 200

        status = await _wait_for_state(client, task_id, "completed")
        assert status["artifact_id"]


@pytest.mark.anyio
async def test_http_approval_deny_blocks_publication() -> None:
    async with _client(_app()) as client:
        created = await client.post(
            "/v1/tasks", json={"text": "high risk task", "needs_human_approval": True}
        )
        task_id = created.json()["task_id"]

        ticket = await _wait_for_approval(client)
        await client.post(f"/v1/approvals/{ticket['ticket_id']}", json={"granted": False})

        status = await _wait_for_state(client, task_id, "failed")
        assert status["failure_reason"] == "approval_denied"
        assert status["artifact_id"] is None
        artifact = await client.get(f"/v1/tasks/{task_id}/artifact")
        assert artifact.status_code == 404


@pytest.mark.anyio
async def test_unknown_resources_return_404() -> None:
    async with _client(_app()) as client:
        assert (await client.get("/v1/tasks/tsk_missing")).status_code == 404
        assert (
            await client.post("/v1/approvals/apv_missing", json={"granted": True})
        ).status_code == 404
        assert (
            await client.post("/v1/tasks", json={"text": "x", "harness": "nope"})
        ).status_code == 404


@pytest.mark.anyio
async def test_eval_endpoint_runs_golden_suite() -> None:
    async with _client(_app()) as client:
        report = await client.post("/v1/evals/run")
        assert report.status_code == 200
        body = report.json()
        assert body["total"] == 5
        assert body["failures"] == []


@pytest.mark.anyio
async def test_completed_task_status_and_artifact_survive_restart(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "events.sqlite3"
    memory_path = tmp_path / "memory.sqlite3"
    artifact_dir = tmp_path / "artifacts"

    async with _client(
        _app(
            store=EventStore(store_path),
            fabric=MemoryFabric(memory_path),
            artifact_dir=artifact_dir,
        )
    ) as client:
        created = await client.post("/v1/tasks", json={"text": "restartable task"})
        task_id = created.json()["task_id"]
        status = await _wait_for_state(client, task_id, "completed")
        assert status["artifact_id"]

    async with _client(
        _app(
            store=EventStore(store_path),
            fabric=MemoryFabric(memory_path),
            artifact_dir=artifact_dir,
        )
    ) as client:
        status_response = await client.get(f"/v1/tasks/{task_id}")
        assert status_response.status_code == 200
        body = status_response.json()
        assert body["state"] == "completed"
        assert body["artifact_id"]
        assert body["critiques"]

        artifact = await client.get(f"/v1/tasks/{task_id}/artifact")
        assert artifact.status_code == 200
        assert artifact.json()["content"]


@pytest.mark.anyio
async def test_publish_approval_can_be_granted_after_restart(tmp_path: Path) -> None:
    store_path = tmp_path / "events.sqlite3"
    memory_path = tmp_path / "memory.sqlite3"
    artifact_dir = tmp_path / "artifacts"

    async with _client(
        _app(
            store=EventStore(store_path),
            fabric=MemoryFabric(memory_path),
            artifact_dir=artifact_dir,
        )
    ) as client:
        created = await client.post(
            "/v1/tasks",
            json={"text": "restartable high risk task", "needs_human_approval": True},
        )
        task_id = created.json()["task_id"]
        ticket = await _wait_for_approval(client)

    async with _client(
        _app(
            store=EventStore(store_path),
            fabric=MemoryFabric(memory_path),
            artifact_dir=artifact_dir,
        )
    ) as client:
        approvals = await client.get("/v1/approvals")
        assert ticket["ticket_id"] in [item["ticket_id"] for item in approvals.json()]

        resolved = await client.post(
            f"/v1/approvals/{ticket['ticket_id']}",
            json={"granted": True, "approver": "boss"},
        )
        assert resolved.status_code == 200

        status = await client.get(f"/v1/tasks/{task_id}")
        assert status.json()["state"] == "completed"
        artifact = await client.get(f"/v1/tasks/{task_id}/artifact")
        assert artifact.status_code == 200
        assert artifact.json()["content"]


def _append_state(
    store: EventStore, task_id: str, current: TaskState, target: TaskState
) -> None:
    store.append(
        Event(
            source="headmaster.tests.api",
            type=EventType.STATE_CHANGED,
            subject=task_id,
            data={"from": current.value, "to": target.value},
        )
    )


def _seed_mid_run_approval(store: EventStore, kind: ApprovalKind) -> ApprovalTicket:
    spec = compile_task(f"restart boundary for {kind}")
    ticket = ApprovalTicket(
        task_id=spec.task_id,
        kind=kind,
        reason=f"{kind} requires a live orchestrator coroutine",
    )
    store.append(
        Event(
            source="headmaster.tests.api",
            type=EventType.TASK_REGISTERED,
            subject=spec.task_id,
            data={"spec": spec.model_dump(mode="json")},
        )
    )
    _append_state(store, spec.task_id, TaskState.REGISTERED, TaskState.CLASSIFIED)
    _append_state(store, spec.task_id, TaskState.CLASSIFIED, TaskState.PLANNED)
    _append_state(store, spec.task_id, TaskState.PLANNED, TaskState.EXECUTING)
    _append_state(
        store,
        spec.task_id,
        TaskState.EXECUTING,
        TaskState.AWAITING_HUMAN_APPROVAL,
    )
    store.append(
        Event(
            source="headmaster.tests.api",
            type=EventType.APPROVAL_REQUESTED,
            subject=spec.task_id,
            data=ticket.model_dump(mode="json"),
        )
    )
    return ticket


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["budget_overrun", "phase_gate"])
async def test_mid_run_approval_grant_after_restart_returns_conflict(
    tmp_path: Path, kind: ApprovalKind
) -> None:
    store_path = tmp_path / f"{kind}.sqlite3"
    store = EventStore(store_path)
    ticket = _seed_mid_run_approval(store, kind)
    store.close()

    async with _client(
        _app(
            store=EventStore(store_path),
            fabric=MemoryFabric(tmp_path / f"{kind}-memory.sqlite3"),
        )
    ) as client:
        approvals = await client.get("/v1/approvals")
        assert ticket.ticket_id in [item["ticket_id"] for item in approvals.json()]

        granted = await client.post(
            f"/v1/approvals/{ticket.ticket_id}",
            json={"granted": True, "approver": "boss"},
        )
        assert granted.status_code == 409
        assert "after restart" in granted.json()["detail"]

        denied = await client.post(
            f"/v1/approvals/{ticket.ticket_id}",
            json={"granted": False, "approver": "boss"},
        )
        assert denied.status_code == 200

        status = await client.get(f"/v1/tasks/{ticket.task_id}")
        assert status.json()["state"] == "failed"
        assert status.json()["failure_reason"] == "approval_denied"


@pytest.mark.anyio
async def test_background_exception_records_failed_event(tmp_path: Path) -> None:
    blocked_artifact_dir = tmp_path / "not_a_directory"
    blocked_artifact_dir.write_text("blocks mkdir", encoding="utf-8")
    async with _client(_app(artifact_dir=blocked_artifact_dir)) as client:
        created = await client.post("/v1/tasks", json={"text": "publish failure"})
        task_id = created.json()["task_id"]

        status = await _wait_for_state(client, task_id, "failed")
        assert status["running"] is False
        assert status["failure_reason"] == "background_task_exception"

        events = await client.get(f"/v1/tasks/{task_id}/events")
        assert any(event["type"] == "task.failed" for event in events.json())
