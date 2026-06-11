"""Approval gateways — the human-in-the-loop boundary.

Safe-by-default: when no gateway is configured, high-risk actions are
denied, never silently approved.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable

from headmaster.schemas.approval import ApprovalDecision, ApprovalTicket


class ApprovalGateway(ABC):
    @abstractmethod
    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision: ...


class StaticApprovalGateway(ApprovalGateway):
    """Fixed decision — used for CLI --approval grant|deny."""

    def __init__(self, *, granted: bool, approver: str = "cli") -> None:
        self._granted = granted
        self._approver = approver

    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision:
        return ApprovalDecision(granted=self._granted, approver=self._approver)


class CallbackApprovalGateway(ApprovalGateway):
    """Programmable decision — used in tests and embedding scenarios."""

    def __init__(self, callback: Callable[[ApprovalTicket], ApprovalDecision]) -> None:
        self._callback = callback
        self.tickets: list[ApprovalTicket] = []

    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision:
        self.tickets.append(ticket)
        return self._callback(ticket)


class QueueApprovalGateway(ApprovalGateway):
    """Parks tickets in a pending queue until resolved out-of-band (HTTP API).

    request() suspends the orchestrator until resolve() supplies a decision.
    """

    def __init__(self) -> None:
        self._pending: dict[str, tuple[ApprovalTicket, asyncio.Future[ApprovalDecision]]] = {}

    def pending(self) -> list[ApprovalTicket]:
        return [ticket for ticket, _ in self._pending.values()]

    def resolve(self, ticket_id: str, decision: ApprovalDecision) -> bool:
        entry = self._pending.get(ticket_id)
        if entry is None:
            return False
        _, future = entry
        if not future.done():
            future.set_result(decision)
        return True

    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision:
        future: asyncio.Future[ApprovalDecision] = asyncio.get_running_loop().create_future()
        self._pending[ticket.ticket_id] = (ticket, future)
        try:
            return await future
        finally:
            self._pending.pop(ticket.ticket_id, None)


class ConsoleApprovalGateway(ApprovalGateway):
    """Interactive y/n prompt; non-interactive sessions resolve to deny."""

    def __init__(self, approver: str = "console") -> None:
        self._approver = approver

    async def request(self, ticket: ApprovalTicket) -> ApprovalDecision:
        prompt = (
            f"[APPROVAL REQUIRED] kind={ticket.kind} task={ticket.task_id}\n"
            f"  reason: {ticket.reason}\n  approve? [y/N]: "
        )
        try:
            answer = input(prompt)
        except EOFError:
            return ApprovalDecision(
                granted=False, approver=self._approver, note="non-interactive: denied"
            )
        return ApprovalDecision(
            granted=answer.strip().lower() in {"y", "yes"}, approver=self._approver
        )
