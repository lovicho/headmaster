"""Audit trail — who decided, based on what, who approved (2nd report mandate).

Derived deterministically from the event log; no separate bookkeeping that
could drift from the source of truth.
"""

import json
from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel

from headmaster.schemas.events import Event, EventType


class AuditEntry(BaseModel):
    time: datetime
    actor: str
    action: str
    basis: str


def build_audit_trail(events: Iterable[Event]) -> list[AuditEntry]:
    trail: list[AuditEntry] = []
    for event in events:
        data = event.data
        if event.type is EventType.CRITIQUE_ISSUED:
            trail.append(
                AuditEntry(
                    time=event.time,
                    actor="critic",
                    action=f"{data.get('status')} {data.get('target_agent')}",
                    basis=json.dumps(data.get("verification_details", {}), ensure_ascii=False),
                )
            )
        elif event.type is EventType.APPROVAL_REQUESTED:
            trail.append(
                AuditEntry(
                    time=event.time,
                    actor="orchestrator",
                    action=f"approval requested ({data.get('kind')})",
                    basis=str(data.get("reason", "")),
                )
            )
        elif event.type in (EventType.APPROVAL_GRANTED, EventType.APPROVAL_DENIED):
            verdict = "granted" if event.type is EventType.APPROVAL_GRANTED else "denied"
            trail.append(
                AuditEntry(
                    time=event.time,
                    actor=str(data.get("approver", "unknown")),
                    action=f"approval {verdict}",
                    basis=str(data.get("note") or data.get("ticket_id", "")),
                )
            )
        elif event.type is EventType.POLICY_DENIED:
            trail.append(
                AuditEntry(
                    time=event.time,
                    actor="policy_engine",
                    action=f"denied tool '{data.get('tool')}' for {data.get('agent')}",
                    basis=str(data.get("reason", "")),
                )
            )
        elif event.type is EventType.BUDGET_EXCEEDED:
            trail.append(
                AuditEntry(
                    time=event.time,
                    actor="budget_ledger",
                    action=f"{data.get('severity')} limit -> {data.get('action')}",
                    basis=json.dumps(
                        {k: v for k, v in data.items() if k not in {"severity", "action"}},
                        ensure_ascii=False,
                    ),
                )
            )
    return trail
