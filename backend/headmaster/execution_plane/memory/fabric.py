"""SQLite-backed memory fabric.

Quarantined records (failed verification) are stored, never discarded,
and excluded from default retrieval — the machine form of the 2nd report's
memory-poisoning defense. Vector search arrives later; retrieval here ranks
by salience x confidence.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from headmaster.schemas.common import MemoryScope
from headmaster.schemas.memory_record import DecayPolicy, MemoryRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_records (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id    TEXT UNIQUE NOT NULL,
    scope        TEXT NOT NULL,
    task_id      TEXT,
    timestamp    TEXT NOT NULL,
    summary      TEXT NOT NULL,
    embedding_ref TEXT,
    salience     REAL NOT NULL,
    confidence   REAL NOT NULL,
    decay_policy TEXT NOT NULL,
    source_refs  TEXT NOT NULL,
    quarantine   INTEGER NOT NULL,
    reuse_count  INTEGER NOT NULL
)
"""

_COLUMNS = (
    "memory_id, scope, task_id, timestamp, summary, embedding_ref,"
    " salience, confidence, decay_policy, source_refs, quarantine, reuse_count"
)

_Row = tuple[
    str, str, str | None, str, str, str | None, float, float, str, str, int, int
]


def _to_record(row: _Row) -> MemoryRecord:
    return MemoryRecord(
        memory_id=row[0],
        scope=MemoryScope(row[1]),
        task_id=row[2],
        timestamp=datetime.fromisoformat(row[3]),
        summary=row[4],
        embedding_ref=row[5],
        salience=row[6],
        confidence=row[7],
        decay_policy=DecayPolicy(row[8]),
        source_refs=json.loads(row[9]),
        quarantine=bool(row[10]),
        reuse_count=row[11],
    )


class MemoryFabric:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if isinstance(path, Path) or path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def write(self, record: MemoryRecord) -> None:
        self._conn.execute(
            f"INSERT INTO memory_records ({_COLUMNS})"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.memory_id,
                record.scope.value,
                record.task_id,
                record.timestamp.isoformat(),
                record.summary,
                record.embedding_ref,
                record.salience,
                record.confidence,
                record.decay_policy.value,
                json.dumps(record.source_refs, ensure_ascii=False),
                int(record.quarantine),
                record.reuse_count,
            ),
        )
        self._conn.commit()

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM memory_records WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return _to_record(row) if row else None

    def search(
        self,
        *,
        scopes: list[MemoryScope] | None = None,
        include_quarantined: bool = False,
        keyword: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if scopes:
            placeholders = ", ".join("?" for _ in scopes)
            clauses.append(f"scope IN ({placeholders})")
            params.extend(scope.value for scope in scopes)
        if not include_quarantined:
            clauses.append("quarantine = 0")
        if keyword:
            clauses.append("summary LIKE ?")
            params.append(f"%{keyword}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM memory_records{where}"
            " ORDER BY salience * confidence DESC, seq DESC LIMIT ?",
            params,
        ).fetchall()
        return [_to_record(row) for row in rows]

    def increment_reuse(self, memory_id: str) -> MemoryRecord | None:
        """Reinforce-on-reuse: bump the reuse counter and return the updated record."""
        self._conn.execute(
            "UPDATE memory_records SET reuse_count = reuse_count + 1 WHERE memory_id = ?",
            (memory_id,),
        )
        self._conn.commit()
        return self.get(memory_id)

    def semantic_exists_for(self, source_memory_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM memory_records WHERE scope = ? AND source_refs LIKE ? LIMIT 1",
            (MemoryScope.SEMANTIC.value, f'%"{source_memory_id}"%'),
        ).fetchone()
        return row is not None

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
