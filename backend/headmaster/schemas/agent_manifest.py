"""AgentManifest — capability, cost and permission declaration of an agent."""

from pydantic import BaseModel, Field

from headmaster.schemas.common import CostTier, MemoryScope


class AgentManifest(BaseModel):
    agent_id: str
    role: str
    capabilities: list[str] = Field(default_factory=list)
    input_schema: str
    output_schema: str
    cost_tier: CostTier = CostTier.MINI
    max_concurrency: int = 1
    requires_tools: list[str] = Field(default_factory=list)
    requires_memory_scopes: list[MemoryScope] = Field(default_factory=list)
    policy_tags: list[str] = Field(default_factory=list)
