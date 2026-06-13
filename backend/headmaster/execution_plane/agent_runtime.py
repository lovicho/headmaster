"""Agent runtime — executes one harnessed agent turn against the model gateway.

Tool use: tools offered to the model are the intersection of the harness
allowlist and the registered gateway tools. Every call passes the policy
engine; denials are fed back to the model as tool results (the agent learns
the boundary instead of crashing). Emits model.called / model.responded /
tool events / artifact.produced so the event log fully covers every
interaction (gate 1-5).
"""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from headmaster.control_plane.harness_compiler import compile_system_prompt
from headmaster.control_plane.policy_engine import PolicyViolationError
from headmaster.execution_plane.models.gateway import (
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelUsage,
)
from headmaster.execution_plane.tools.tool_gateway import ToolGateway
from headmaster.schemas.common import CostTier
from headmaster.schemas.events import Event, EventType
from headmaster.schemas.evidence_bundle import EvidenceBundle, IBFProof
from headmaster.schemas.harness_manifest import AgentHarness, IBFRequirements
from headmaster.schemas.memory_record import MemoryRecord
from headmaster.schemas.task_spec import TaskSpec
from headmaster.schemas.environment import EnvironmentContext

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
    def __init__(
        self,
        gateway: ModelGateway,
        tool_gateway: ToolGateway | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self._gateway = gateway
        self._tool_gateway = tool_gateway
        self._max_tool_rounds = max_tool_rounds

    async def _run_tool_calls(
        self,
        *,
        harness: AgentHarness,
        task: TaskSpec,
        calls: list[Any],
        emit: EmitFn,
    ) -> list[ModelMessage]:
        assert self._tool_gateway is not None
        results: list[ModelMessage] = []
        for call in calls:
            try:
                outcome = await self._tool_gateway.call(
                    harness=harness,
                    tool_name=call.name,
                    arguments=call.arguments,
                    task_id=task.task_id,
                    emit=emit,
                )
                result_text = str(outcome)
            except PolicyViolationError as err:
                result_text = f"DENIED by policy: {err.reason}"
            except KeyError as err:
                result_text = f"TOOL ERROR: {err}"
            results.append(
                ModelMessage(role="tool", content=result_text, tool_call_id=call.call_id)
            )
        return results

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
        env_context: EnvironmentContext | None = None,
    ) -> AgentDraft:
        system_prompt = compile_system_prompt(harness, requirements)
        if env_context and env_context.system_prompt_extension:
            system_prompt += f"\n\n# Execution Environment\nProvider: {env_context.provider_name}\nCapabilities: {', '.join(env_context.native_capabilities)}\n\n{env_context.system_prompt_extension}"
        
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
        tools = self._tool_gateway.specs_for(harness) if self._tool_gateway else []
        messages = [
            ModelMessage(role="system", content=system_prompt),
            ModelMessage(role="user", content="\n\n".join(user_sections)),
        ]
        total_usage = ModelUsage()
        rounds = 0
        while True:
            request = ModelRequest(
                messages=list(messages), cost_tier=effective_tier, tools=tools
            )
            provider, model = self._gateway.resolve(effective_tier)
            emit(
                Event(
                    source="headmaster.agent_runtime",
                    type=EventType.MODEL_CALLED,
                    subject=task.task_id,
                    data={
                        "agent": harness.harness_id,
                        "provider": provider,
                        "model": model,
                        "round": rounds,
                    },
                )
            )
            response = await self._gateway.complete(request)
            total_usage = ModelUsage(
                input_tokens=total_usage.input_tokens + response.usage.input_tokens,
                output_tokens=total_usage.output_tokens + response.usage.output_tokens,
            )
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
                        "tool_calls": len(response.tool_calls),
                        "text": response.text,
                    },
                )
            )
            if (
                response.tool_calls
                and self._tool_gateway is not None
                and rounds < self._max_tool_rounds
            ):
                rounds += 1
                messages.append(
                    ModelMessage(
                        role="assistant",
                        content=response.text,
                        tool_calls=response.tool_calls,
                    )
                )
                messages.extend(
                    await self._run_tool_calls(
                        harness=harness, task=task, calls=response.tool_calls, emit=emit
                    )
                )
                continue
            break

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
            usage=total_usage,
        )
