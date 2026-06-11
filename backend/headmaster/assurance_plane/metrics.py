"""Operational metrics computed from the event log (plan/03 section 5)."""

from pydantic import BaseModel

from headmaster.control_plane.budget_ledger import PricingTable
from headmaster.schemas.events import EventType
from headmaster.storage.event_store import EventStore


class Metrics(BaseModel):
    total_tasks: int
    completed: int
    failed: int
    task_success_rate: float
    critiques_approved: int
    critiques_rejected: int
    zero_shot_detections: int
    evidence_coverage: float
    model_calls: int
    input_tokens: int
    output_tokens: int
    est_cost_usd: float


def compute_metrics(store: EventStore, pricing: PricingTable | None = None) -> Metrics:
    pricing = pricing or {}
    completed: set[str] = set()
    failed: set[str] = set()
    critiques_approved = 0
    critiques_rejected = 0
    zero_shot = 0
    proofed_artifacts = 0
    artifacts = 0
    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    cost = 0.0

    for event in store.all_events():
        task_id = event.subject or ""
        if event.type is EventType.TASK_COMPLETED:
            completed.add(task_id)
        elif event.type is EventType.TASK_FAILED:
            failed.add(task_id)
        elif event.type is EventType.CRITIQUE_ISSUED:
            if event.data.get("status") == "APPROVED":
                critiques_approved += 1
            else:
                critiques_rejected += 1
            if event.data.get("zero_shot_detected"):
                zero_shot += 1
        elif event.type is EventType.ARTIFACT_PRODUCED:
            artifacts += 1
            if event.data.get("has_ibf_proof"):
                proofed_artifacts += 1
        elif event.type is EventType.MODEL_RESPONDED:
            model_calls += 1
            usage = event.data.get("usage", {})
            in_tok = int(usage.get("input_tokens", 0))
            out_tok = int(usage.get("output_tokens", 0))
            input_tokens += in_tok
            output_tokens += out_tok
            provider_models = pricing.get(str(event.data.get("provider", "")), {})
            price = provider_models.get(str(event.data.get("model", ""))) or provider_models.get(
                "default"
            )
            if price is not None:
                cost += (
                    in_tok / 1_000_000 * price.input_per_mtok
                    + out_tok / 1_000_000 * price.output_per_mtok
                )

    total = len(completed | failed)
    return Metrics(
        total_tasks=total,
        completed=len(completed),
        failed=len(failed),
        task_success_rate=round(len(completed) / total, 4) if total else 0.0,
        critiques_approved=critiques_approved,
        critiques_rejected=critiques_rejected,
        zero_shot_detections=zero_shot,
        evidence_coverage=round(proofed_artifacts / artifacts, 4) if artifacts else 0.0,
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        est_cost_usd=round(cost, 6),
    )
