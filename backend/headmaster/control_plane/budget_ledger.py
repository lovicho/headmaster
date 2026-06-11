"""Budget ledger — per-task cost/token accounting with two thresholds:

- soft limit (ratio of the hard limit): downgrade the model tier
- hard limit: halt and require human approval to continue

Limits come from TaskSpec.constraints.budget; prices from config/models.yaml.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from headmaster.execution_plane.models.gateway import CONFIG_DIR, ModelUsage
from headmaster.schemas.common import CostTier
from headmaster.schemas.task_spec import Budget

_DOWNGRADE: dict[CostTier, CostTier] = {
    CostTier.HEAVY: CostTier.STANDARD,
    CostTier.STANDARD: CostTier.MINI,
    CostTier.MINI: CostTier.MINI,
}


class ModelPrice(BaseModel):
    input_per_mtok: float
    output_per_mtok: float


PricingTable = dict[str, dict[str, ModelPrice]]


class BudgetConfig(BaseModel):
    pricing: PricingTable = Field(default_factory=dict)
    soft_ratio: float = 0.8


def load_budget_config(path: Path | None = None) -> BudgetConfig:
    config_path = path or (CONFIG_DIR / "models.yaml")
    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return BudgetConfig.model_validate(
        {
            "pricing": raw.get("pricing", {}),
            "soft_ratio": raw.get("budget", {}).get("soft_ratio", 0.8),
        }
    )


class BudgetStatus(BaseModel):
    spent_usd: float
    tokens: int
    model_calls: int
    soft_exceeded: bool
    hard_exceeded: bool


class BudgetLedger:
    def __init__(
        self,
        *,
        budget: Budget,
        pricing: PricingTable | None = None,
        soft_ratio: float = 0.8,
    ) -> None:
        self._budget = budget
        self._pricing = pricing or {}
        self._soft_ratio = soft_ratio
        self._spent_usd = 0.0
        self._tokens = 0
        self._model_calls = 0

    def _price(self, provider: str, model: str) -> ModelPrice | None:
        models = self._pricing.get(provider)
        if not models:
            return None
        return models.get(model) or models.get("default")

    def record_model_usage(self, provider: str, model: str, usage: ModelUsage) -> None:
        self._model_calls += 1
        self._tokens += usage.input_tokens + usage.output_tokens
        price = self._price(provider, model)
        if price is not None:
            self._spent_usd += (
                usage.input_tokens / 1_000_000 * price.input_per_mtok
                + usage.output_tokens / 1_000_000 * price.output_per_mtok
            )

    def _exceeded(self, ratio: float) -> bool:
        cost_cap = self._budget.max_model_cost_usd
        token_cap = self._budget.max_tokens
        if cost_cap is not None and self._spent_usd >= cost_cap * ratio:
            return True
        return token_cap is not None and self._tokens >= token_cap * ratio

    def soft_exceeded(self) -> bool:
        return self._exceeded(self._soft_ratio)

    def hard_exceeded(self) -> bool:
        return self._exceeded(1.0)

    def effective_tier(self, requested: CostTier) -> tuple[CostTier, bool]:
        """Downgrade one tier once the soft threshold is crossed."""
        if self.soft_exceeded() and requested is not CostTier.MINI:
            return _DOWNGRADE[requested], True
        return requested, False

    def status(self) -> BudgetStatus:
        return BudgetStatus(
            spent_usd=round(self._spent_usd, 6),
            tokens=self._tokens,
            model_calls=self._model_calls,
            soft_exceeded=self.soft_exceeded(),
            hard_exceeded=self.hard_exceeded(),
        )
