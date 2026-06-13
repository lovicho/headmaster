"""PostgreSQL-backed memory fabric.

Provides the same interface as MemoryFabric, but uses SQLAlchemy 2.0 with a PostgreSQL
database for robust multi-node support.
"""

from datetime import datetime
from collections.abc import Sequence

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    create_engine,
    select,
    update,
    desc,
    func
)
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

from headmaster.schemas.common import MemoryScope
from headmaster.schemas.memory_record import DecayPolicy, MemoryRecord

Base = declarative_base()

class MemoryRecordModel(Base):
    __tablename__ = "memory_records"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(String, unique=True, nullable=False)
    scope = Column(String, nullable=False)
    task_id = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    embedding_ref = Column(String, nullable=True)
    salience = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    decay_policy = Column(String, nullable=False)
    source_refs = Column(JSONB, nullable=False)
    quarantine = Column(Boolean, nullable=False)
    reuse_count = Column(Integer, nullable=False)


class PostgresMemoryFabric:
    """PostgreSQL implementation of the MemoryFabric interface."""

    def __init__(self, connection_url: str) -> None:
        """Initialize with a SQLAlchemy PostgreSQL connection URL.
        
        Example: postgresql+psycopg2://user:pass@localhost:5432/headmaster
        """
        self._engine = create_engine(connection_url, echo=False)
        Base.metadata.create_all(self._engine)

    def _to_record(self, model: MemoryRecordModel) -> MemoryRecord:
        return MemoryRecord(
            memory_id=model.memory_id,
            scope=MemoryScope(model.scope),
            task_id=model.task_id,
            timestamp=datetime.fromisoformat(model.timestamp),
            summary=model.summary,
            embedding_ref=model.embedding_ref,
            salience=model.salience,
            confidence=model.confidence,
            decay_policy=DecayPolicy(model.decay_policy),
            source_refs=model.source_refs,
            quarantine=model.quarantine,
            reuse_count=model.reuse_count,
        )

    def write(self, record: MemoryRecord) -> None:
        with Session(self._engine) as session:
            model = MemoryRecordModel(
                memory_id=record.memory_id,
                scope=record.scope.value,
                task_id=record.task_id,
                timestamp=record.timestamp.isoformat(),
                summary=record.summary,
                embedding_ref=record.embedding_ref,
                salience=record.salience,
                confidence=record.confidence,
                decay_policy=record.decay_policy.value,
                source_refs=record.source_refs,
                quarantine=record.quarantine,
                reuse_count=record.reuse_count,
            )
            session.add(model)
            session.commit()

    def get(self, memory_id: str) -> MemoryRecord | None:
        with Session(self._engine) as session:
            stmt = select(MemoryRecordModel).where(MemoryRecordModel.memory_id == memory_id)
            model = session.scalars(stmt).first()
            return self._to_record(model) if model else None

    def search(
        self,
        *,
        scopes: list[MemoryScope] | None = None,
        include_quarantined: bool = False,
        keyword: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        with Session(self._engine) as session:
            stmt = select(MemoryRecordModel)
            if scopes:
                stmt = stmt.where(MemoryRecordModel.scope.in_([s.value for s in scopes]))
            if not include_quarantined:
                stmt = stmt.where(MemoryRecordModel.quarantine == False)
            if keyword:
                stmt = stmt.where(MemoryRecordModel.summary.ilike(f"%{keyword}%"))
            
            stmt = stmt.order_by(
                desc(MemoryRecordModel.salience * MemoryRecordModel.confidence),
                desc(MemoryRecordModel.seq)
            ).limit(limit)
            
            models = session.scalars(stmt).all()
            return [self._to_record(m) for m in models]

    def increment_reuse(self, memory_id: str) -> MemoryRecord | None:
        with Session(self._engine) as session:
            stmt = update(MemoryRecordModel).where(
                MemoryRecordModel.memory_id == memory_id
            ).values(reuse_count=MemoryRecordModel.reuse_count + 1)
            session.execute(stmt)
            session.commit()
            
            # Fetch the updated record
            return self.get(memory_id)

    def semantic_exists_for(self, source_memory_id: str) -> bool:
        with Session(self._engine) as session:
            # PostgreSQL JSONB supports exact matching or containment,
            # but for simple list of strings, we can use JSONB's array containment `?` or just query Python-side.
            # However, SQLAlchemy has JSONB operators. Let's do a naive string match fallback if we must,
            # but JSONB @> is better.
            stmt = select(MemoryRecordModel).where(
                MemoryRecordModel.scope == MemoryScope.SEMANTIC.value,
                MemoryRecordModel.source_refs.cast(String).like(f'%"{source_memory_id}"%')
            ).limit(1)
            model = session.scalars(stmt).first()
            return model is not None

    def count(self) -> int:
        with Session(self._engine) as session:
            return session.scalar(select(func.count(MemoryRecordModel.seq))) or 0

    def close(self) -> None:
        self._engine.dispose()
