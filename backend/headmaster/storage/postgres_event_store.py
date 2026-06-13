"""PostgreSQL-backed event store.

Provides the same interface as EventStore, but uses SQLAlchemy 2.0 with a PostgreSQL
database for robust multi-node support.
"""

from datetime import datetime
from collections.abc import Sequence

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

from headmaster.schemas.events import Event, EventType

Base = declarative_base()

class EventModel(Base):
    __tablename__ = "events"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    time = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    data = Column(JSONB, nullable=False)


class PostgresEventStore:
    """PostgreSQL implementation of the EventStore interface."""

    def __init__(self, connection_url: str) -> None:
        """Initialize with a SQLAlchemy PostgreSQL connection URL.
        
        Example: postgresql+psycopg2://user:pass@localhost:5432/headmaster
        """
        self._engine = create_engine(connection_url, echo=False)
        Base.metadata.create_all(self._engine)

    def append(self, event: Event) -> None:
        with Session(self._engine) as session:
            model = EventModel(
                id=event.id,
                type=event.type.value,
                source=event.source,
                time=event.time.isoformat(),
                subject=event.subject,
                data=event.data,
            )
            session.add(model)
            session.commit()

    def _models_to_events(self, models: Sequence[EventModel]) -> list[Event]:
        return [
            Event(
                id=m.id,
                type=EventType(m.type),
                source=m.source,
                time=datetime.fromisoformat(m.time),
                subject=m.subject,
                data=m.data,
            )
            for m in models
        ]

    def for_task(self, task_id: str) -> list[Event]:
        with Session(self._engine) as session:
            stmt = select(EventModel).where(EventModel.subject == task_id).order_by(EventModel.seq)
            models = session.scalars(stmt).all()
            return self._models_to_events(models)

    def all_events(self) -> list[Event]:
        with Session(self._engine) as session:
            stmt = select(EventModel).order_by(EventModel.seq)
            models = session.scalars(stmt).all()
            return self._models_to_events(models)

    def task_ids(self) -> list[str]:
        with Session(self._engine) as session:
            stmt = select(EventModel.subject).where(EventModel.subject.is_not(None)).distinct().order_by(EventModel.subject)
            return list(session.scalars(stmt).all())

    def close(self) -> None:
        self._engine.dispose()
