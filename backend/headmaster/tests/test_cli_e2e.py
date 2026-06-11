"""Phase 1 gates 1-1 / 1-6: full CLI run works offline (no API keys)."""

from pathlib import Path

from headmaster.cli import main
from headmaster.schemas import TaskState
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_final_state


def test_cli_run_and_replay_offline(tmp_path: Path, capsys: object) -> None:
    store_path = tmp_path / "events.sqlite3"
    exit_code = main(
        [
            "run",
            "오프라인 데모 작업",
            "--provider",
            "fake",
            "--store",
            str(store_path),
            "--memory-store",
            str(tmp_path / "memory.sqlite3"),
            "--artifact-dir",
            str(tmp_path / "artifacts"),
        ]
    )
    assert exit_code == 0
    artifacts = list((tmp_path / "artifacts").glob("tsk_*.md"))
    assert len(artifacts) == 1

    store = EventStore(store_path)
    task_ids = store.task_ids()
    assert len(task_ids) == 1
    assert replay_final_state(store.for_task(task_ids[0])) is TaskState.COMPLETED
    store.close()

    assert main(["replay", task_ids[0], "--store", str(store_path)]) == 0


def test_cli_unknown_harness_fails(tmp_path: Path) -> None:
    exit_code = main(
        [
            "run",
            "x",
            "--harness",
            "nonexistent",
            "--provider",
            "fake",
            "--store",
            str(tmp_path / "e.sqlite3"),
            "--memory-store",
            str(tmp_path / "m.sqlite3"),
            "--artifact-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 1
