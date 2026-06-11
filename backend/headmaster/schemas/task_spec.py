"""TaskSpec — canonical machine representation of a user request."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from headmaster.schemas.common import DataSensitivity, Language, RiskLevel, new_id


class Budget(BaseModel):
    max_model_cost_usd: float | None = None
    max_tool_calls: int | None = None
    max_tokens: int | None = None


class Constraints(BaseModel):
    language: Language = Language.KO
    deadline: datetime | None = None
    budget: Budget = Field(default_factory=Budget)
    quality_criteria: list[str] = Field(default_factory=list)


class RiskProfile(BaseModel):
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    action_risk: RiskLevel = RiskLevel.LOW
    needs_human_approval: bool = False


class TaskInput(BaseModel):
    type: Literal["file", "url", "text"]
    ref: str
    trust: Literal["user_provided", "system", "external"] = "user_provided"


class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("tsk"))
    title: str
    intent: str
    constraints: Constraints = Field(default_factory=Constraints)
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)
    inputs: list[TaskInput] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    policy_checks: list[str] = Field(default_factory=list)
