"""Phase 4c: self-improvement loop — diagnose, propose, validate, promote."""

import asyncio
import shutil
from pathlib import Path

from headmaster.assurance_plane.critic_service import CriticService
from headmaster.assurance_plane.self_improvement import (
    analyze_failures,
    apply_patch,
    bump_patch_version,
    promote_patch,
    propose_patches,
    validate_patch,
)
from headmaster.control_plane.harness_registry import TEMPLATES_DIR, load_all, load_harness
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import FakeAdapter, ModelGateway, load_routing
from headmaster.execution_plane.orchestrator import Orchestrator
from headmaster.schemas import AgentHarness
from headmaster.storage.event_store import EventStore
from headmaster.tests.test_orchestrator import NO_PROOF_RESPONSE

GOLDEN = Path(__file__).resolve().parent / "golden" / "critic_golden.json"


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def _store_with_failures() -> EventStore:
    """Produce a store containing repeated zero-shot rejections for 'content'."""
    store = EventStore()
    gateway = ModelGateway(
        load_routing(),
        {"fake": FakeAdapter([NO_PROOF_RESPONSE] * 3)},
        provider_override="fake",
    )
    orchestrator = Orchestrator(
        store=store,
        agent_runtime=AgentRuntime(gateway),
        critic=CriticService(),
        registry=_registry(),
        max_revisions=2,
    )
    asyncio.run(orchestrator.run_task(compile_task("실패 유도 작업"), "content"))
    return store


def test_analyze_failures_finds_recurring_pattern() -> None:
    report = analyze_failures(_store_with_failures())
    assert report.total_rejections == 3
    keys = {(p.harness_id, p.issue_type) for p in report.patterns}
    assert ("content", "zero_shot_invention") in keys


def test_propose_and_apply_patch() -> None:
    registry = _registry()
    report = analyze_failures(_store_with_failures())
    patches = propose_patches(report, registry)
    assert patches, "recurring pattern must yield a patch proposal"
    patch = next(p for p in patches if p.harness_id == "content")
    assert "REINFORCED" in patch.directive

    original = registry["content"]
    patched = apply_patch(original, patch)
    assert patch.directive in patched.inherited_directives
    assert patched.version == bump_patch_version(original.version)
    # proposing again against the patched registry is a no-op (idempotent)
    repropose = propose_patches(report, {**registry, "content": patched})
    assert all(
        p.harness_id != "content" or p.directive != patch.directive for p in repropose
    )


def test_validate_patch_against_golden_suite() -> None:
    registry = _registry()
    patches = propose_patches(analyze_failures(_store_with_failures()), registry)
    patch = next(p for p in patches if p.harness_id == "content")
    assert validate_patch(patch, registry, GOLDEN) is True


def test_promote_patch_writes_versioned_template(tmp_path: Path) -> None:
    templates = tmp_path / "harnesses"
    templates.mkdir()
    shutil.copy(TEMPLATES_DIR / "content.yaml", templates / "content.yaml")

    registry = _registry()
    patches = propose_patches(analyze_failures(_store_with_failures()), registry)
    patch = next(p for p in patches if p.harness_id == "content")

    written = promote_patch(patch, registry, templates, GOLDEN)
    assert written is not None

    promoted = load_harness(written)
    assert isinstance(promoted, AgentHarness)
    assert patch.directive in promoted.inherited_directives
    assert promoted.version == bump_patch_version(registry["content"].version)

    # second promotion of the same patch is blocked (idempotent)
    assert promote_patch(patch, registry, templates, GOLDEN) is None


def test_bump_patch_version() -> None:
    assert bump_patch_version("8.0.0") == "8.0.1"
    assert bump_patch_version("1.2.9") == "1.2.10"
