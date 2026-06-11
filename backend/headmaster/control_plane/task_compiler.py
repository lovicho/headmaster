"""Task compiler — normalizes a raw user request into a TaskSpec.

Phase 1 is rule-based (no LLM): defaults plus explicit flags. An
LLM-assisted classifier can replace internals later without changing
the TaskSpec contract.
"""

from headmaster.schemas.common import Language
from headmaster.schemas.task_spec import Constraints, RiskProfile, TaskSpec

_TITLE_MAX = 60


def compile_task(
    text: str,
    *,
    language: Language = Language.KO,
    needs_human_approval: bool = False,
) -> TaskSpec:
    stripped = " ".join(text.split())
    if not stripped:
        raise ValueError("task text must not be empty")
    title = stripped if len(stripped) <= _TITLE_MAX else stripped[: _TITLE_MAX - 1] + "…"
    return TaskSpec(
        title=title,
        intent=stripped,
        constraints=Constraints(language=language),
        risk_profile=RiskProfile(needs_human_approval=needs_human_approval),
    )
