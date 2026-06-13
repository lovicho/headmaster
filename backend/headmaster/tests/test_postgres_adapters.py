"""Tests for PostgreSQL adapters.

These tests require a running PostgreSQL instance. 
Run them with: pytest test_postgres_adapters.py
"""

import os
import pytest
from datetime import datetime

from headmaster.schemas.events import Event, EventType
from headmaster.schemas.common import MemoryScope
from headmaster.schemas.memory_record import MemoryRecord, DecayPolicy

from headmaster.storage.postgres_event_store import PostgresEventStore
from headmaster.execution_plane.memory.postgres_fabric import PostgresMemoryFabric

# To run tests, set POSTGRES_URL=postgresql+psycopg2://user:pass@localhost:5432/test_db
TEST_DB_URL = os.environ.get("POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="POSTGRES_URL environment variable not set"
)

def test_postgres_event_store_roundtrip():
    store = PostgresEventStore(TEST_DB_URL)
    
    event = Event(
        source="test",
        type=EventType.TASK_REGISTERED,
        subject="task-123",
        data={"key": "value"}
    )
    
    store.append(event)
    events = store.for_task("task-123")
    
    assert len(events) >= 1
    assert any(e.id == event.id for e in events)
    assert any(e.subject == "task-123" for e in events)
    assert any(e.data == {"key": "value"} for e in events)
    
    store.close()

def test_postgres_memory_fabric_roundtrip():
    fabric = PostgresMemoryFabric(TEST_DB_URL)
    
    record = MemoryRecord(
        scope=MemoryScope.EPISODIC,
        summary="Test episode",
        salience=0.8,
        confidence=0.9,
        quarantine=False
    )
    
    fabric.write(record)
    loaded = fabric.get(record.memory_id)
    
    assert loaded is not None
    assert loaded.memory_id == record.memory_id
    assert loaded.summary == "Test episode"
    assert loaded.scope == MemoryScope.EPISODIC
    
    results = fabric.search(keyword="Test")
    assert any(r.memory_id == record.memory_id for r in results)
    
    fabric.increment_reuse(record.memory_id)
    updated = fabric.get(record.memory_id)
    assert updated.reuse_count == 1
    
    fabric.close()
