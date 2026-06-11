"""Phase 4a gates: control API end-to-end over ASGI (offline, fake provider).

- task submission -> background run -> status/events/artifact
- HTTP approval queue: high-risk task blocks until approved/denied via API
"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from headmaster.api.main import create_app
from headmaster.execution_plane.memory import MemoryFabric
from headmaster.storage.event_store import EventStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app() -> FastAPI:
    return create_app(store=EventStore(), fabric=MemoryFabric(), provider="fake")


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
        created = await client.post("/v1/tasks", json={"text": "API 데모 작업"})
        assert created.status_code == 200
        task_id = created.json()["task_id"]

        status = await _wait_for_state(client, task_id, "completed")
        assert status["running"] is False
        assert status["artifact_id"]

        events = await client.get(f"/v1/tasks/{task_id}/events")
        assert events.status_code == 200
        assert any(e["type"] == "task.completed" for e in events.json())

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
            "/v1/tasks", json={"text": "고위험 작업", "needs_human_approval": True}
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
            "/v1/tasks", json={"text": "고위험 작업", "needs_human_approval": True}
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
