"""SQLite-backed event store — the source of truth for all task state.

Append-only. Replay never re-calls models: it folds recorded events,
so recovery is deterministic.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from headmaster.schemas.events import Event, EventType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    id      TEXT UNIQUE NOT NULL,
    type    TEXT NOT NULL,
    source  TEXT NOT NULL,
    time    TEXT NOT NULL,
    subject TEXT,
    data    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    task_id TEXT PRIMARY KEY,
    last_seq INTEGER NOT NULL,
    data TEXT NOT NULL
);
"""


class EventStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if isinstance(path, Path) or path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, event: Event) -> None:
        self._conn.execute(
            "INSERT INTO events (id, type, source, time, subject, data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.type.value,
                event.source,
                event.time.isoformat(),
                event.subject,
                json.dumps(event.data, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def _rows_to_events(
        self, rows: list[tuple[str, str, str, str, str | None, str]]
    ) -> list[Event]:
        return [
            Event(
                id=row[0],
                type=EventType(row[1]),
                source=row[2],
                time=datetime.fromisoformat(row[3]),
                subject=row[4],
                data=json.loads(row[5]),
            )
            for row in rows
        ]

    def for_task(self, task_id: str) -> list[Event]:
        rows = self._conn.execute(
            "SELECT id, type, source, time, subject, data FROM events"
            " WHERE subject = ? ORDER BY seq",
            (task_id,),
        ).fetchall()
        return self._rows_to_events(rows)


    def for_task_since_with_seq(self, task_id: str, seq: int) -> list[tuple[int, Event]]:
        rows = self._conn.execute(
            "SELECT seq, id, type, source, time, subject, data FROM events"
            " WHERE subject = ? AND seq > ? ORDER BY seq",
            (task_id, seq),
        ).fetchall()
        return [(row[0], self._rows_to_events([row[1:]])[0]) for row in rows]

    def save_snapshot(self, task_id: str, last_seq: int, data: dict) -> None:
        self._conn.execute(
            "INSERT INTO snapshots (task_id, last_seq, data) VALUES (?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET last_seq=excluded.last_seq, data=excluded.data",
            (task_id, last_seq, json.dumps(data, ensure_ascii=False)),
        )
        self._conn.commit()

    def load_snapshot(self, task_id: str) -> tuple[int, dict] | None:
        row = self._conn.execute(
            "SELECT last_seq, data FROM snapshots WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return (row[0], json.loads(row[1]))


    def events_of_types(self, types: list[str]) -> list[Event]:
        if not types:
            return []
        placeholders = ",".join("?" for _ in types)
        rows = self._conn.execute(
            f"SELECT id, type, source, time, subject, data FROM events WHERE type IN ({placeholders}) ORDER BY seq",
            tuple(types),
        ).fetchall()
        return self._rows_to_events(rows)

    def all_events(self) -> list[Event]:
        rows = self._conn.execute(
            "SELECT id, type, source, time, subject, data FROM events ORDER BY seq"
        ).fetchall()
        return self._rows_to_events(rows)

    def task_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT subject FROM events WHERE subject IS NOT NULL ORDER BY subject"
        ).fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        self._conn.close()
