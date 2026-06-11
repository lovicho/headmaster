"""Agent runtime — executes one harnessed agent turn against the model gateway.

Emits model.called / model.responded / artifact.produced events so the
event log fully covers every model interaction (gate 1-5).
"""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from headmaster.control_plane.harness_compiler import compile_system_prompt
from headmaster.execution_plane.models.gateway import (
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelUsage,
)
from headmaster.schemas.common import CostTier
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.evidence_bundle import EvidenceBundle, IBFProof
from headmaster.schemas.harness_manifest import AgentHarness, IBFRequirements
from headmaster.schemas.memory_record import MemoryRecord
from headmaster.schemas.task_spec import TaskSpec

EmitFn = Callable[[Event], None]

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of a single JSON object from model output."""
    candidates = [text.strip()]
    fenced = _FENCED_JSON.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class AgentDraft(BaseModel):
    bundle: EvidenceBundle
    content: str
    raw_text: str
    provider: str
    model: str
    usage: ModelUsage


class AgentRuntime:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    async def run(
        self,
        *,
        harness: AgentHarness,
        task: TaskSpec,
        requirements: IBFRequirements,
        revision_notes: list[str],
        emit: EmitFn,
        supplied_assets: list[MemoryRecord] | None = None,
        cost_tier: CostTier | None = None,
    ) -> AgentDraft:
        system_prompt = compile_system_prompt(harness, requirements)
        user_sections = [f"# Task\n{task.intent}"]
        if supplied_assets:
            user_sections.append(
                "# Internal Assets [Mandatory_Imitation_Base]\n"
                + "\n".join(
                    f"- {asset.memory_id}: {asset.summary}" for asset in supplied_assets
                )
                + "\nWhen you imitate these assets, cite their ids in"
                " ibf_proof.imitated_assets."
            )
        if task.success_criteria:
            user_sections.append(
                "# Success Criteria\n" + "\n".join(f"- {c}" for c in task.success_criteria)
            )
        if revision_notes:
            user_sections.append(
                "# Mandatory Revisions (previous draft was REJECTED)\n"
                + "\n".join(f"- {note}" for note in revision_notes)
            )
        effective_tier = cost_tier or harness.cost_tier
        request = ModelRequest(
            messages=[
                ModelMessage(role="system", content=system_prompt),
                ModelMessage(role="user", content="\n\n".join(user_sections)),
            ],
            cost_tier=effective_tier,
        )
        provider, model = self._gateway.resolve(effective_tier)
        emit(
            Event(
                source="headmaster.agent_runtime",
                type=EventType.MODEL_CALLED,
                subject=task.task_id,
                data={"agent": harness.harness_id, "provider": provider, "model": model},
            )
        )
        response = await self._gateway.complete(request)
        emit(
            Event(
                source="headmaster.agent_runtime",
                type=EventType.MODEL_RESPONDED,
                subject=task.task_id,
                data={
                    "agent": harness.harness_id,
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage.model_dump(),
                    "stop_reason": response.stop_reason,
                    "text": response.text,
                },
            )
        )

        parsed = extract_json_object(response.text)
        proof: IBFProof | None = None
        content = response.text
        if parsed is not None:
            raw_proof = parsed.get("ibf_proof")
            if raw_proof is not None:
                try:
                    proof = IBFProof.model_validate(raw_proof)
                except ValidationError:
                    proof = None
            raw_content = parsed.get("content")
            if isinstance(raw_content, str) and raw_content.strip():
                content = raw_content

        bundle = EvidenceBundle(task_id=task.task_id, ibf_proof=proof)
        emit(
            Event(
                source="headmaster.agent_runtime",
                type=EventType.ARTIFACT_PRODUCED,
                subject=task.task_id,
                data={
                    "agent": harness.harness_id,
                    "bundle_id": bundle.bundle_id,
                    "has_ibf_proof": proof is not None,
                },
            )
        )
        return AgentDraft(
            bundle=bundle,
            content=content,
            raw_text=response.text,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
        )
