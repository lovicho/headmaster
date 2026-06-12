"""Subprocess-level restart checks for the control API."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(tmp_path: Path, port: int) -> subprocess.Popen[str]:
    backend_dir = Path(__file__).resolve().parents[2]
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "headmaster.cli",
            "serve",
            "--provider",
            "fake",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--store",
            str(tmp_path / "events.sqlite3"),
            "--memory-store",
            str(tmp_path / "memory.sqlite3"),
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--static-dir",
            str(tmp_path / "missing-static"),
        ],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _wait_ready(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 20
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=1.0) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout is not None else ""
                raise AssertionError(f"server exited early:\n{output}")
            try:
                response = client.get("/v1/metrics")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    raise AssertionError("server did not become ready")


def _wait_for_state(
    client: httpx.Client, task_id: str, *states: str, timeout: float = 10.0
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/tasks/{task_id}")
        body: dict[str, object] = response.json()
        if response.status_code == 200 and body["state"] in states:
            return body
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} never reached {states}: {body}")


def test_completed_task_survives_subprocess_restart(tmp_path: Path) -> None:
    first_port = _free_port()
    first = _start_server(tmp_path, first_port)
    try:
        _wait_ready(first, first_port)
        with httpx.Client(
            base_url=f"http://127.0.0.1:{first_port}", timeout=5.0
        ) as client:
            created = client.post("/v1/tasks", json={"text": "subprocess restart"})
            assert created.status_code == 200
            task_id = str(created.json()["task_id"])
            status = _wait_for_state(client, task_id, "completed")
            assert status["artifact_id"]
    finally:
        _stop_server(first)

    second_port = _free_port()
    second = _start_server(tmp_path, second_port)
    try:
        _wait_ready(second, second_port)
        with httpx.Client(
            base_url=f"http://127.0.0.1:{second_port}", timeout=5.0
        ) as client:
            replayed_status = client.get(f"/v1/tasks/{task_id}")
            assert replayed_status.status_code == 200
            assert replayed_status.json()["state"] == "completed"

            artifact = client.get(f"/v1/tasks/{task_id}/artifact")
            assert artifact.status_code == 200
            assert artifact.json()["content"]
    finally:
        _stop_server(second)
