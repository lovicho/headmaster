"""Orchestrator — drives the task state machine through the core loop:

    supply knowledge -> plan -> execute -> critique -> (repair | publish -> assimilate)

Every state transition and every model/tool interaction is emitted as an
event; the event log is the single source of truth (replayable).

Assurance plane (Phase 3):
- high-risk tasks (needs_human_approval) cannot publish without an approval
  gateway decision; no gateway configured means deny, never silent approval
- budget soft limit downgrades the model tier; hard limit halts and requires
  human approval to continue
- run_orchestra executes a multi-agent OrchestraHarness: phases run in order,
  agents inside a phase fan out in parallel, only rejected agents retry, and
  phase gates (critic/human) guard advancement
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from headmaster.assurance_plane.approval_gateway import ApprovalGateway
from headmaster.assurance_plane.critic_service import CriticService, requirements_for
from headmaster.control_plane.budget_ledger import BudgetLedger, PricingTable
from headmaster.execution_plane.agent_runtime import AgentDraft, AgentRuntime
from headmaster.execution_plane.memory.knowledge_manager import KnowledgeManager
from headmaster.schemas.approval import ApprovalDecision, ApprovalTicket
from headmaster.schemas.artifact import Artifact, content_sha256
from headmaster.schemas.critique_report import CritiqueReport
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.harness_manifest import (
    AgentHarness,
    IBFRequirements,
    OrchestraHarness,
)
from headmaster.schemas.memory_record import MemoryRecord
from headmaster.schemas.states import TaskState, validate_transition
from headmaster.schemas.task_spec import TaskSpec
from headmaster.storage.event_store import EventStore

SOURCE = "headmaster.orchestrator"


class OrchestratorResult(BaseModel):
    task_id: str
    final_state: TaskState
    artifact: Artifact | None = None
    critiques: list[CritiqueReport] = []
    artifact_path: str | None = None
    supplied_asset_ids: list[str] = []
    reused_asset_ids: list[str] = []
    failure_reason: str | None = None


class Orchestrator:
    def __init__(
        self,
        *,
        store: EventStore,
        agent_runtime: AgentRuntime,
        critic: CriticService,
        registry: dict[str, AgentHarness],
        knowledge_manager: KnowledgeManager | None = None,
        approval_gateway: ApprovalGateway | None = None,
        pricing: PricingTable | None = None,
        soft_ratio: float = 0.8,
        max_revisions: int = 2,
        artifact_dir: Path | None = None,
    ) -> None:
        self._store = store
        self._agent_runtime = agent_runtime
        self._critic = critic
        self._registry = registry
        self._km = knowledge_manager
        self._approval = approval_gateway
        self._pricing = pricing or {}
        self._soft_ratio = soft_ratio
        self._max_revisions = max_revisions
        self._artifact_dir = artifact_dir

    # ----- primitives -------------------------------------------------

    def _emit(self, task_id: str, event_type: EventType, data: dict[str, object]) -> None:
        self._store.append(
            Event(source=SOURCE, type=event_type, subject=task_id, data=dict(data))
        )

    def _transition(self, task_id: str, current: TaskState, target: TaskState) -> TaskState:
        validate_transition(current, target)
        self._emit(
            task_id,
            EventType.STATE_CHANGED,
            {"from": current.value, "to": target.value},
        )
        return target

    def _ledger_for(self, spec: TaskSpec) -> BudgetLedger:
        return BudgetLedger(
            budget=spec.constraints.budget,
            pricing=self._pricing,
            soft_ratio=self._soft_ratio,
        )

    async def _request_approval(self, ticket: ApprovalTicket) -> ApprovalDecision:
        self._emit(
            ticket.task_id, EventType.APPROVAL_REQUESTED, ticket.model_dump(mode="json")
        )
        if self._approval is None:
            decision = ApprovalDecision(
                granted=False,
                approver="none_configured",
                note="no approval gateway configured — denied by default",
            )
        else:
            decision = await self._approval.request(ticket)
        self._emit(
            ticket.task_id,
            EventType.APPROVAL_GRANTED if decision.granted else EventType.APPROVAL_DENIED,
            {"ticket_id": ticket.ticket_id, **decision.model_dump(mode="json")},
        )
        return decision

    def _supply_knowledge(self, spec: TaskSpec) -> list[MemoryRecord]:
        supplied = self._km.supply(spec) if self._km else []
        self._emit(
            spec.task_id,
            EventType.KNOWLEDGE_SUPPLIED,
            {
                "asset_ids": [record.memory_id for record in supplied],
                "count": len(supplied),
                "bootstrap": not supplied,
            },
        )
        return supplied

    @staticmethod
    def _effective_requirements(
        harness: AgentHarness, supplied: list[MemoryRecord]
    ) -> IBFRequirements:
        """Bootstrap rule: relax the imitation requirement when nothing was supplied."""
        requirements = requirements_for(harness)
        if requirements.must_reference_internal_assets and not supplied:
            return requirements.model_copy(update={"must_reference_internal_assets": False})
        return requirements

    async def _execute_agent(
        self,
        *,
        spec: TaskSpec,
        harness: AgentHarness,
        requirements: IBFRequirements,
        revision_notes: list[str],
        supplied: list[MemoryRecord],
        supplied_ids: set[str],
        ledger: BudgetLedger,
        soft_announced: set[str],
    ) -> tuple[AgentDraft, CritiqueReport]:
        tier, downgraded = ledger.effective_tier(harness.cost_tier)
        if downgraded and harness.harness_id not in soft_announced:
            soft_announced.add(harness.harness_id)
            self._emit(
                spec.task_id,
                EventType.BUDGET_EXCEEDED,
                {
                    "severity": "soft",
                    "action": "downgrade_tier",
                    "agent": harness.harness_id,
                    "from": harness.cost_tier.value,
                    "to": tier.value,
                },
            )
        draft = await self._agent_runtime.run(
            harness=harness,
            task=spec,
            requirements=requirements,
            revision_notes=revision_notes,
            emit=self._store.append,
            supplied_assets=supplied,
            cost_tier=tier,
        )
        ledger.record_model_usage(draft.provider, draft.model, draft.usage)
        critique = self._critic.review(
            target_agent=harness.harness_id,
            bundle=draft.bundle,
            requirements=requirements,
            task_id=spec.task_id,
            supplied_asset_ids=supplied_ids if supplied_ids else None,
        )
        self._emit(spec.task_id, EventType.CRITIQUE_ISSUED, critique.model_dump(mode="json"))
        return draft, critique

    async def _check_hard_budget(
        self,
        *,
        spec: TaskSpec,
        state: TaskState,
        ledger: BudgetLedger,
        overrun_approved: bool,
    ) -> tuple[TaskState, bool, bool]:
        """Returns (state, overrun_approved, halted)."""
        if overrun_approved or not ledger.hard_exceeded():
            return state, overrun_approved, False
        status = ledger.status()
        self._emit(
            spec.task_id,
            EventType.BUDGET_EXCEEDED,
            {"severity": "hard", "action": "halt_and_require_approval", **status.model_dump()},
        )
        state = self._transition(spec.task_id, state, TaskState.AWAITING_HUMAN_APPROVAL)
        decision = await self._request_approval(
            ApprovalTicket(
                task_id=spec.task_id,
                kind="budget_overrun",
                reason="hard budget limit exceeded — approval required to continue",
                details=status.model_dump(),
            )
        )
        if not decision.granted:
            state = self._transition(spec.task_id, state, TaskState.FAILED)
            self._emit(
                spec.task_id,
                EventType.TASK_FAILED,
                {"reason": "budget_hard_limit_denied", **status.model_dump()},
            )
            return state, overrun_approved, True
        state = self._transition(spec.task_id, state, TaskState.EXECUTING)
        return state, True, False

    def _publish(
        self,
        *,
        spec: TaskSpec,
        produced_by: str,
        output_format: str,
        content: str,
        evidence_bundle_id: str,
        critique_id: str | None,
    ) -> tuple[Artifact, str | None]:
        artifact = Artifact(
            task_id=spec.task_id,
            produced_by=produced_by,
            format=output_format,
            content=content,
            content_hash=content_sha256(content),
            evidence_bundle_id=evidence_bundle_id,
            critique_id=critique_id,
        )
        artifact_path: str | None = None
        if self._artifact_dir is not None:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            path = self._artifact_dir / f"{spec.task_id}.md"
            path.write_text(artifact.content, encoding="utf-8")
            artifact_path = str(path)
        self._emit(
            spec.task_id,
            EventType.ARTIFACT_PUBLISHED,
            {
                "artifact_id": artifact.artifact_id,
                "content_hash": artifact.content_hash,
                "path": artifact_path,
            },
        )
        return artifact, artifact_path

    def _assimilate(
        self,
        *,
        spec: TaskSpec,
        harness_id: str,
        artifact: Artifact | None,
        critique: CritiqueReport,
        reused: list[str],
    ) -> None:
        promoted: list[MemoryRecord] = []
        records: list[MemoryRecord] = []
        if self._km is not None:
            promoted = self._km.record_reuse(reused) if reused else []
            records = self._km.maintain(
                task=spec, harness_id=harness_id, artifact=artifact, critique=critique
            )
        self._emit(
            spec.task_id,
            EventType.KNOWLEDGE_ASSIMILATED,
            {
                "records": [record.memory_id for record in records],
                "reused_assets": reused,
                "promoted": [record.memory_id for record in promoted],
                "quarantined": artifact is None,
            },
        )

    def _fail(
        self, spec: TaskSpec, state: TaskState, reason: str, **extra: object
    ) -> TaskState:
        state = self._transition(spec.task_id, state, TaskState.FAILED)
        self._emit(spec.task_id, EventType.TASK_FAILED, {"reason": reason, **extra})
        return state

    # ----- single-agent loop -------------------------------------------

    async def run_task(self, spec: TaskSpec, harness_id: str) -> OrchestratorResult:
        harness = self._registry.get(harness_id)
        if harness is None:
            raise KeyError(f"unknown agent harness: {harness_id}")
        task_id = spec.task_id
        state = TaskState.REGISTERED
        self._emit(task_id, EventType.TASK_REGISTERED, {"spec": spec.model_dump(mode="json")})

        state = self._transition(task_id, state, TaskState.CLASSIFIED)
        self._emit(task_id, EventType.TASK_CLASSIFIED, {"harness_id": harness_id})
        self._emit(
            task_id,
            EventType.HARNESS_COMPILED,
            {"harness_id": harness_id, "version": harness.version},
        )
        supplied = self._supply_knowledge(spec)
        supplied_ids = {record.memory_id for record in supplied}
        requirements = self._effective_requirements(harness, supplied)
        ledger = self._ledger_for(spec)
        soft_announced: set[str] = set()
        overrun_approved = False

        state = self._transition(task_id, state, TaskState.PLANNED)
        self._emit(task_id, EventType.PLAN_CREATED, {"steps": [harness_id], "revision": 0})

        critiques: list[CritiqueReport] = []
        revision_notes: list[str] = []
        attempt = 0
        while True:
            state = self._transition(task_id, state, TaskState.EXECUTING)
            state, overrun_approved, halted = await self._check_hard_budget(
                spec=spec, state=state, ledger=ledger, overrun_approved=overrun_approved
            )
            if halted:
                return OrchestratorResult(
                    task_id=task_id,
                    final_state=state,
                    critiques=critiques,
                    supplied_asset_ids=sorted(supplied_ids),
                    failure_reason="budget_hard_limit_denied",
                )
            self._emit(
                task_id,
                EventType.AGENT_DISPATCHED,
                {"agent": harness_id, "attempt": attempt},
            )
            draft, critique = await self._execute_agent(
                spec=spec,
                harness=harness,
                requirements=requirements,
                revision_notes=revision_notes,
                supplied=supplied,
                supplied_ids=supplied_ids,
                ledger=ledger,
                soft_announced=soft_announced,
            )
            state = self._transition(task_id, state, TaskState.CRITIQUING)
            critiques.append(critique)

            if critique.accepted:
                if spec.risk_profile.needs_human_approval:
                    state = self._transition(
                        task_id, state, TaskState.AWAITING_HUMAN_APPROVAL
                    )
                    decision = await self._request_approval(
                        ApprovalTicket(
                            task_id=task_id,
                            kind="publish",
                            reason=f"high-risk task requests publication of"
                            f" {harness_id} deliverable",
                            details={"critique_id": critique.critique_id},
                        )
                    )
                    if not decision.granted:
                        state = self._fail(spec, state, "approval_denied")
                        return OrchestratorResult(
                            task_id=task_id,
                            final_state=state,
                            critiques=critiques,
                            supplied_asset_ids=sorted(supplied_ids),
                            failure_reason="approval_denied",
                        )
                    state = self._transition(task_id, state, TaskState.VALIDATED)
                else:
                    state = self._transition(task_id, state, TaskState.VALIDATED)
                state = self._transition(task_id, state, TaskState.PUBLISHING)
                artifact, artifact_path = self._publish(
                    spec=spec,
                    produced_by=harness_id,
                    output_format=harness.output_contract.format,
                    content=draft.content,
                    evidence_bundle_id=draft.bundle.bundle_id,
                    critique_id=critique.critique_id,
                )
                state = self._transition(task_id, state, TaskState.ASSIMILATING)
                proof = draft.bundle.ibf_proof
                reused = [
                    asset
                    for asset in (proof.imitated_assets if proof else [])
                    if asset in supplied_ids
                ]
                self._assimilate(
                    spec=spec,
                    harness_id=harness_id,
                    artifact=artifact,
                    critique=critique,
                    reused=reused,
                )
                state = self._transition(task_id, state, TaskState.COMPLETED)
                self._emit(task_id, EventType.TASK_COMPLETED, {"attempts": attempt + 1})
                return OrchestratorResult(
                    task_id=task_id,
                    final_state=state,
                    artifact=artifact,
                    critiques=critiques,
                    artifact_path=artifact_path,
                    supplied_asset_ids=sorted(supplied_ids),
                    reused_asset_ids=reused,
                )

            if attempt >= self._max_revisions:
                self._assimilate(
                    spec=spec,
                    harness_id=harness_id,
                    artifact=None,
                    critique=critique,
                    reused=[],
                )
                state = self._fail(
                    spec,
                    state,
                    "critic_rejected_max_revisions",
                    attempts=attempt + 1,
                )
                return OrchestratorResult(
                    task_id=task_id,
                    final_state=state,
                    critiques=critiques,
                    supplied_asset_ids=sorted(supplied_ids),
                    failure_reason="critic_rejected_max_revisions",
                )

            attempt += 1
            revision_notes = list(critique.mandatory_revisions)
            state = self._transition(task_id, state, TaskState.REPLANNING)
            self._emit(
                task_id,
                EventType.REPLAN_TRIGGERED,
                {"revisions": revision_notes, "attempt": attempt},
            )
            state = self._transition(task_id, state, TaskState.PLANNED)
            self._emit(
                task_id, EventType.PLAN_CREATED, {"steps": [harness_id], "revision": attempt}
            )

    # ----- multi-agent orchestra (fan-out) -----------------------------

    async def run_orchestra(
        self, spec: TaskSpec, orchestra: OrchestraHarness
    ) -> OrchestratorResult:
        missing = [
            role
            for phase in orchestra.phases
            for role in phase.agents
            if role not in self._registry
        ]
        if missing:
            raise KeyError(f"unknown agent harnesses in orchestra: {sorted(set(missing))}")

        task_id = spec.task_id
        state = TaskState.REGISTERED
        self._emit(task_id, EventType.TASK_REGISTERED, {"spec": spec.model_dump(mode="json")})
        state = self._transition(task_id, state, TaskState.CLASSIFIED)
        self._emit(
            task_id,
            EventType.TASK_CLASSIFIED,
            {"orchestra_id": orchestra.harness_id, "task_class": orchestra.task_class},
        )
        self._emit(
            task_id,
            EventType.HARNESS_COMPILED,
            {"harness_id": orchestra.harness_id, "version": orchestra.version},
        )
        supplied = self._supply_knowledge(spec)
        supplied_ids = {record.memory_id for record in supplied}
        ledger = self._ledger_for(spec)
        soft_announced: set[str] = set()
        overrun_approved = False

        state = self._transition(task_id, state, TaskState.PLANNED)
        self._emit(
            task_id,
            EventType.PLAN_CREATED,
            {"phases": [phase.phase_id for phase in orchestra.phases], "revision": 0},
        )

        critiques: list[CritiqueReport] = []
        sections: list[str] = []
        reused_total: set[str] = set()
        last_bundle_id = ""
        last_critique: CritiqueReport | None = None

        for index, phase in enumerate(orchestra.phases):
            is_last = index == len(orchestra.phases) - 1
            pending: dict[str, list[str]] = {agent: [] for agent in phase.agents}
            approved_drafts: dict[str, AgentDraft] = {}
            attempt = 0
            while True:
                state = self._transition(task_id, state, TaskState.EXECUTING)
                state, overrun_approved, halted = await self._check_hard_budget(
                    spec=spec, state=state, ledger=ledger, overrun_approved=overrun_approved
                )
                if halted:
                    return OrchestratorResult(
                        task_id=task_id,
                        final_state=state,
                        critiques=critiques,
                        supplied_asset_ids=sorted(supplied_ids),
                        failure_reason="budget_hard_limit_denied",
                    )
                agents = sorted(pending)
                for agent_id in agents:
                    self._emit(
                        task_id,
                        EventType.AGENT_DISPATCHED,
                        {"agent": agent_id, "phase": phase.phase_id, "attempt": attempt},
                    )
                results = await asyncio.gather(
                    *(
                        self._execute_agent(
                            spec=spec,
                            harness=self._registry[agent_id],
                            requirements=self._effective_requirements(
                                self._registry[agent_id], supplied
                            ),
                            revision_notes=pending[agent_id],
                            supplied=supplied,
                            supplied_ids=supplied_ids,
                            ledger=ledger,
                            soft_announced=soft_announced,
                        )
                        for agent_id in agents
                    )
                )
                state = self._transition(task_id, state, TaskState.CRITIQUING)
                rejected: dict[str, list[str]] = {}
                for agent_id, (draft, critique) in zip(agents, results, strict=True):
                    critiques.append(critique)
                    last_critique = critique
                    if critique.accepted:
                        approved_drafts[agent_id] = draft
                        last_bundle_id = draft.bundle.bundle_id
                    else:
                        rejected[agent_id] = list(critique.mandatory_revisions)
                if not rejected:
                    break
                if attempt >= self._max_revisions:
                    if last_critique is not None:
                        self._assimilate(
                            spec=spec,
                            harness_id=orchestra.harness_id,
                            artifact=None,
                            critique=last_critique,
                            reused=[],
                        )
                    state = self._fail(
                        spec,
                        state,
                        "critic_rejected_max_revisions",
                        phase=phase.phase_id,
                        agents=sorted(rejected),
                    )
                    return OrchestratorResult(
                        task_id=task_id,
                        final_state=state,
                        critiques=critiques,
                        supplied_asset_ids=sorted(supplied_ids),
                        failure_reason="critic_rejected_max_revisions",
                    )
                attempt += 1
                pending = rejected
                state = self._transition(task_id, state, TaskState.REPLANNING)
                self._emit(
                    task_id,
                    EventType.REPLAN_TRIGGERED,
                    {"phase": phase.phase_id, "agents": sorted(rejected), "attempt": attempt},
                )
                state = self._transition(task_id, state, TaskState.PLANNED)
                self._emit(
                    task_id,
                    EventType.PLAN_CREATED,
                    {"phases": [phase.phase_id], "revision": attempt},
                )

            for agent_id in phase.agents:
                draft = approved_drafts[agent_id]
                sections.append(f"## [{phase.phase_id}/{agent_id}]\n\n{draft.content}")
                proof = draft.bundle.ibf_proof
                if proof:
                    reused_total.update(
                        asset for asset in proof.imitated_assets if asset in supplied_ids
                    )

            needs_human_gate = (phase.gate is not None and phase.gate.approver == "human") or (
                is_last and spec.risk_profile.needs_human_approval
            )
            if needs_human_gate:
                state = self._transition(task_id, state, TaskState.AWAITING_HUMAN_APPROVAL)
                gate_id = phase.gate.gate_id if phase.gate else "final_publish"
                decision = await self._request_approval(
                    ApprovalTicket(
                        task_id=task_id,
                        kind="phase_gate",
                        reason=f"orchestra phase gate '{gate_id}'"
                        f" ({phase.phase_id}) requires human approval",
                        details={"phase": phase.phase_id, "gate": gate_id},
                    )
                )
                if not decision.granted:
                    state = self._fail(
                        spec, state, "approval_denied", phase=phase.phase_id
                    )
                    return OrchestratorResult(
                        task_id=task_id,
                        final_state=state,
                        critiques=critiques,
                        supplied_asset_ids=sorted(supplied_ids),
                        failure_reason="approval_denied",
                    )
                state = self._transition(
                    task_id,
                    state,
                    TaskState.VALIDATED if is_last else TaskState.PLANNED,
                )
            else:
                state = self._transition(
                    task_id,
                    state,
                    TaskState.VALIDATED if is_last else TaskState.PLANNED,
                )
            if not is_last:
                next_phase = orchestra.phases[index + 1]
                self._emit(
                    task_id,
                    EventType.PLAN_CREATED,
                    {"phases": [next_phase.phase_id], "revision": 0},
                )

        state = self._transition(task_id, state, TaskState.PUBLISHING)
        combined = "\n\n---\n\n".join(sections)
        assert last_critique is not None
        artifact, artifact_path = self._publish(
            spec=spec,
            produced_by=orchestra.harness_id,
            output_format="markdown",
            content=combined,
            evidence_bundle_id=last_bundle_id,
            critique_id=last_critique.critique_id,
        )
        state = self._transition(task_id, state, TaskState.ASSIMILATING)
        self._assimilate(
            spec=spec,
            harness_id=orchestra.harness_id,
            artifact=artifact,
            critique=last_critique,
            reused=sorted(reused_total),
        )
        state = self._transition(task_id, state, TaskState.COMPLETED)
        self._emit(
            task_id,
            EventType.TASK_COMPLETED,
            {"phases": len(orchestra.phases), "agents": len(critiques)},
        )
        return OrchestratorResult(
            task_id=task_id,
            final_state=state,
            artifact=artifact,
            critiques=critiques,
            artifact_path=artifact_path,
            supplied_asset_ids=sorted(supplied_ids),
            reused_asset_ids=sorted(reused_total),
        )
