"""HarnessManifest — a harness is a policy-compiled execution contract, not a prompt bundle.

Two kinds:
- AgentHarness: machine form of one v8 individual agent harness.
- OrchestraHarness: machine form of the Master Orchestrator harness
  (task-class level: phases, gates, required roles).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from headmaster.schemas.common import CostTier, Language, RiskLevel


class LanguagePolicy(BaseModel):
    """English-Core / Korean-Edge: internal reasoning in EN, client-facing output per task."""

    internal: Language = Language.EN
    external: Language = Language.KO


class Persona(BaseModel):
    role: str
    objective: str


class IBFProtocol(BaseModel):
    """Imitate -> Benchmark -> Fusion -> Maintain loop (v8 core).

    Roles may omit steps that do not apply, but at least one must be present.
    """

    imitate: str | None = None
    benchmark: str | None = None
    fusion: str | None = None
    maintain: str | None = None

    @model_validator(mode="after")
    def at_least_one_step(self) -> "IBFProtocol":
        if not any([self.imitate, self.benchmark, self.fusion, self.maintain]):
            raise ValueError("IBFProtocol requires at least one step defined")
        return self


class OutputContract(BaseModel):
    format: Literal["json", "markdown", "json+markdown"]
    schema_ref: str | None = None
    description: str | None = None


class ToolPolicy(BaseModel):
    mcp_allowed: list[str] = Field(default_factory=list)
    sandbox_required: bool = False
    external_write_requires_human_approval: bool = True


class AgentHarness(BaseModel):
    kind: Literal["agent"] = "agent"
    harness_id: str
    version: str
    role: str
    persona: Persona
    inherited_directives: list[str] = Field(min_length=1)
    ibf_protocol: IBFProtocol
    output_contract: OutputContract
    language_policy: LanguagePolicy = Field(default_factory=LanguagePolicy)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    cost_tier: CostTier = CostTier.MINI


class PhaseGate(BaseModel):
    gate_id: str
    description: str
    approver: Literal["critic", "human", "secops_qa"]


class OrchestraPhase(BaseModel):
    phase_id: str
    title: str
    agents: list[str] = Field(min_length=1)
    description: str
    gate: PhaseGate | None = None


class IBFRequirements(BaseModel):
    must_reference_internal_assets: bool = True
    must_reference_external_benchmarks: bool = True
    proof_format: list[str] = Field(
        default_factory=lambda: ["asset_ids", "benchmark_uris", "trace_ids", "artifact_hashes"]
    )


class OrchestraHarness(BaseModel):
    kind: Literal["orchestra"] = "orchestra"
    harness_id: str
    version: str
    task_class: str
    risk_tier: RiskLevel = RiskLevel.MEDIUM
    core_directives: list[str] = Field(min_length=1)
    required_roles: list[str] = Field(min_length=1)
    phases: list[OrchestraPhase] = Field(min_length=1)
    ibf_requirements: IBFRequirements = Field(default_factory=IBFRequirements)
    approval_gates: list[str] = Field(default_factory=list)
    language_policy: LanguagePolicy = Field(default_factory=LanguagePolicy)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    eval_suite: list[str] = Field(default_factory=list)
    rollback_policy: str | None = None


Harness = Annotated[AgentHarness | OrchestraHarness, Field(discriminator="kind")]

harness_adapter: TypeAdapter[AgentHarness | OrchestraHarness] = TypeAdapter(Harness)
