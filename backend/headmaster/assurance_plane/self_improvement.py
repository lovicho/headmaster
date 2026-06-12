"""Self-improvement loop (3rd report): observe -> diagnose -> propose -> promote.

Recurring failure patterns in the event log produce harness directive
patches. A patch is promoted to the harness template ONLY after the golden
suite passes with the patch applied (conservative gate — memory/harness
poisoning defense), and every promotion bumps the harness semver patch level
so it is auditable in version control.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from headmaster.assurance_plane.evaluator import run_golden_suite
from headmaster.schemas.common import new_id
from headmaster.schemas.events import EventType
from headmaster.schemas.harness_manifest import AgentHarness
from headmaster.storage.event_store import EventStore

_DIRECTIVE_BY_ISSUE: dict[str, str] = {
    "HM-ZS-001": (
        "REINFORCED: every deliverable MUST attach I-B-F proof before review;"
        " blank-canvas outputs without provenance are rejected immediately."
    ),
    "HM-EV-001": (
        "REINFORCED: when imitation is required, declare the exact internal"
        " [Mandatory_Imitation_Base] asset ids used."
    ),
    "HM-EV-002": (
        "REINFORCED: never invent internal asset ids; reference only assets supplied"
        " in [Mandatory_Imitation_Base]."
    ),
    "HM-EV-003": (
        "REINFORCED: when benchmarking is required, declare the exact external"
        " benchmark URI list used."
    ),
    "HM-LG-001": (
        "REINFORCED: always explain the fusion methodology — how client-specific facts"
        " were merged into the imitated/benchmarked skeleton."
    ),
    "zero_shot_invention": (
        "REINFORCED: every deliverable MUST cite its imitation/benchmark sources in"
        " ibf_proof; outputs without provenance are rejected without review."
    ),
    "missing_evidence": (
        "REINFORCED: declare every imitated asset id and benchmark URI actually used;"
        " never reference assets that were not supplied."
    ),
    "logic_gap": (
        "REINFORCED: always explain the fusion methodology — how client-specific facts"
        " were merged into the imitated/benchmarked skeleton."
    ),
    "format_error": (
        "REINFORCED: the output must exactly match the declared output contract schema."
    ),
    "policy_violation": (
        "REINFORCED: check the policy pack before acting; never exceed the tool"
        " allowlist or write externally without approval."
    ),
}


class FailurePattern(BaseModel):
    harness_id: str
    issue_type: str
    rejection_code: str | None = None
    category: str | None = None
    count: int
    critique_ids: list[str] = Field(default_factory=list)


class FailureReport(BaseModel):
    total_rejections: int
    patterns: list[FailurePattern] = Field(default_factory=list)


class HarnessPatch(BaseModel):
    patch_id: str = Field(default_factory=lambda: new_id("pch"))
    harness_id: str
    kind: Literal["add_directive"] = "add_directive"
    directive: str
    rationale: str
    evidence_count: int


def analyze_failures(store: EventStore, *, min_count: int = 2) -> FailureReport:
    """Diagnose: group rejected critiques by (agent, issue type)."""
    buckets: dict[tuple[str, str, str | None, str | None], list[str]] = {}
    total = 0
    for event in store.all_events():
        if event.type is not EventType.CRITIQUE_ISSUED:
            continue
        if event.data.get("status") != "REJECTED":
            continue
        total += 1
        agent = str(event.data.get("target_agent", ""))
        critique_id = str(event.data.get("critique_id", ""))
        issues: set[tuple[str, str | None, str | None]] = set()
        findings = event.data.get("findings", [])
        if isinstance(findings, list):
            for finding in findings:
                if not isinstance(finding, dict) or "issue_type" not in finding:
                    continue
                code = finding.get("code")
                category = finding.get("category")
                issues.add(
                    (
                        str(finding["issue_type"]),
                        str(code) if code is not None else None,
                        str(category) if category is not None else None,
                    )
                )
        if event.data.get("zero_shot_detected") and not issues:
            issues.add(("zero_shot_invention", None, None))
        for issue, code, category in issues:
            buckets.setdefault((agent, issue, code, category), []).append(critique_id)
    patterns = [
        FailurePattern(
            harness_id=agent,
            issue_type=issue,
            rejection_code=code,
            category=category,
            count=len(ids),
            critique_ids=ids,
        )
        for (agent, issue, code, category), ids in sorted(buckets.items())
        if len(ids) >= min_count
    ]
    patterns.sort(key=lambda pattern: pattern.count, reverse=True)
    return FailureReport(total_rejections=total, patterns=patterns)


def propose_patches(
    report: FailureReport, registry: dict[str, AgentHarness]
) -> list[HarnessPatch]:
    """Propose: one directive patch per recurring (agent, issue) pattern."""
    patches: list[HarnessPatch] = []
    for pattern in report.patterns:
        harness = registry.get(pattern.harness_id)
        directive_key = pattern.rejection_code or pattern.issue_type
        directive = _DIRECTIVE_BY_ISSUE.get(directive_key)
        if harness is None or directive is None:
            continue
        if directive in harness.inherited_directives:
            continue  # already applied in a previous improvement round
        patches.append(
            HarnessPatch(
                harness_id=pattern.harness_id,
                directive=directive,
                rationale=(
                    f"{directive_key} rejected {pattern.count}x for"
                    f" '{pattern.harness_id}'"
                ),
                evidence_count=pattern.count,
            )
        )
    return patches


def bump_patch_version(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def apply_patch(harness: AgentHarness, patch: HarnessPatch) -> AgentHarness:
    """Apply in-memory (used for validation and for the live registry)."""
    return harness.model_copy(
        update={
            "inherited_directives": [*harness.inherited_directives, patch.directive],
            "version": bump_patch_version(harness.version),
        }
    )


def validate_patch(
    patch: HarnessPatch, registry: dict[str, AgentHarness], golden_path: Path
) -> bool:
    """Conservative gate: the golden suite must stay green with the patch applied."""
    harness = registry.get(patch.harness_id)
    if harness is None:
        return False
    patched = dict(registry)
    patched[patch.harness_id] = apply_patch(harness, patch)
    return run_golden_suite(golden_path, patched).ok


def promote_patch(
    patch: HarnessPatch,
    registry: dict[str, AgentHarness],
    templates_dir: Path,
    golden_path: Path,
) -> Path | None:
    """Promote: persist the validated patch into the harness YAML template.

    Returns the written path, or None when blocked (validation failed,
    template missing, or directive already present).
    """
    if not validate_patch(patch, registry, golden_path):
        return None
    template_path = templates_dir / f"{patch.harness_id}.yaml"
    if not template_path.is_file():
        return None
    with template_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    directives = raw.get("inherited_directives", [])
    if patch.directive in directives:
        return None
    raw["inherited_directives"] = [*directives, patch.directive]
    raw["version"] = bump_patch_version(str(raw["version"]))
    AgentHarness.model_validate(raw)  # never write an invalid template
    with template_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False, width=100)
    return template_path
