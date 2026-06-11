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
)
"""


class EventStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if isinstance(path, Path) or path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(_SCHEMA)
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
