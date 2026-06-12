"""Headmaster CLI.

    headmaster run "<task text>" [--harness content | --orchestra b2b_website_v8]
                   [--provider fake] [--approval prompt|grant|deny] ...
    headmaster replay <task_id> [--store PATH]
    headmaster metrics [--store PATH]
    headmaster eval [--golden PATH]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from headmaster.assurance_plane.approval_gateway import (
    ApprovalGateway,
    ConsoleApprovalGateway,
    StaticApprovalGateway,
)
from headmaster.assurance_plane.critic_service import CriticService
from headmaster.assurance_plane.evaluator import assert_no_regression, run_golden_suite
from headmaster.assurance_plane.metrics import compute_metrics
from headmaster.control_plane.budget_ledger import load_budget_config
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.control_plane.topology_selector import select_topology
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.memory import KnowledgeManager, MemoryFabric
from headmaster.execution_plane.models import (
    AgyCliAdapter,
    AnthropicAdapter,
    FakeAdapter,
    GeminiCliAdapter,
    ModelAdapter,
    ModelGateway,
    OpenAIAdapter,
    load_routing,
)
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.execution_plane.tools import build_default_tool_gateway
from headmaster.schemas.harness_manifest import AgentHarness, OrchestraHarness
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_states

_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_DEFAULT_GOLDEN = Path(__file__).resolve().parent / "tests" / "golden" / "critic_golden.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headmaster")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one task through the orchestrator")
    run.add_argument("text", help="task description (natural language)")
    run.add_argument("--harness", default="content", help="agent harness id (default: content)")
    run.add_argument("--orchestra", default=None, help="orchestra harness id (multi-agent run)")
    run.add_argument(
        "--provider",
        default=None,
        choices=["anthropic", "openai", "agy", "gemini", "fake"],
        help="override the model provider (agy/gemini = Google OAuth via local CLI,"
        " fake = offline demo)",
    )
    run.add_argument(
        "--approval",
        default="prompt",
        choices=["prompt", "grant", "deny"],
        help="approval mode for human gates (default: interactive prompt)",
    )
    run.add_argument("--store", default="./data/events.sqlite3", help="event store path")
    run.add_argument(
        "--memory-store", default="./data/memory.sqlite3", help="memory fabric path"
    )
    run.add_argument("--artifact-dir", default="./data/artifacts", help="artifact output dir")
    run.add_argument("--max-revisions", type=int, default=2)

    replay = sub.add_parser("replay", help="replay the state sequence of a task")
    replay.add_argument("task_id")
    replay.add_argument("--store", default="./data/events.sqlite3", help="event store path")

    metrics = sub.add_parser("metrics", help="compute operational metrics from the event log")
    metrics.add_argument("--store", default="./data/events.sqlite3", help="event store path")

    eval_cmd = sub.add_parser("eval", help="run the golden-set regression suite")
    eval_cmd.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="golden set path")

    serve = sub.add_parser("serve", help="start the control API (FastAPI/uvicorn)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8400)
    serve.add_argument(
        "--provider",
        default=None,
        choices=["anthropic", "openai", "agy", "gemini", "fake"],
        help="override the model provider (agy/gemini = Google OAuth via local CLI,"
        " fake = offline demo)",
    )
    serve.add_argument("--store", default="./data/events.sqlite3", help="event store path")
    serve.add_argument(
        "--memory-store", default="./data/memory.sqlite3", help="memory fabric path"
    )
    serve.add_argument("--artifact-dir", default="./data/artifacts", help="artifact output dir")
    serve.add_argument(
        "--static-dir",
        default="../frontend/dist",
        help="dashboard static files dir (ignored when missing)",
    )

    improve = sub.add_parser(
        "improve", help="analyze failures and propose/promote harness patches"
    )
    improve.add_argument("--store", default="./data/events.sqlite3", help="event store path")
    improve.add_argument("--min-count", type=int, default=2, help="pattern threshold")
    improve.add_argument(
        "--apply",
        action="store_true",
        help="promote validated patches into harness templates (default: dry-run)",
    )
    improve.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="golden set path")
    return parser


def _make_gateway(provider_override: str | None) -> ModelGateway:
    routing = load_routing()
    adapters: dict[str, ModelAdapter] = {
        "anthropic": AnthropicAdapter(),
        "openai": OpenAIAdapter(),
        "agy": AgyCliAdapter(),
        "gemini": GeminiCliAdapter(),
        "fake": FakeAdapter(),
    }
    return ModelGateway(routing, adapters, provider_override=provider_override)


def _make_approval_gateway(mode: str) -> ApprovalGateway:
    if mode == "grant":
        return StaticApprovalGateway(granted=True)
    if mode == "deny":
        return StaticApprovalGateway(granted=False)
    return ConsoleApprovalGateway()


async def _run(args: argparse.Namespace) -> int:
    provider: str | None = args.provider
    if provider in _KEY_ENV and not os.environ.get(_KEY_ENV[provider]):
        print(f"error: {_KEY_ENV[provider]} is not set (or use --provider fake)")
        return 1
    all_harnesses = load_all()
    registry = {
        harness_id: harness
        for harness_id, harness in all_harnesses.items()
        if isinstance(harness, AgentHarness)
    }
    orchestra: OrchestraHarness | None = None
    if args.orchestra is not None:
        candidate = all_harnesses.get(args.orchestra)
        if not isinstance(candidate, OrchestraHarness):
            print(f"error: unknown orchestra '{args.orchestra}'")
            return 1
        orchestra = candidate
    elif args.harness not in registry:
        print(f"error: unknown harness '{args.harness}' (available: {sorted(registry)})")
        return 1

    budget_config = load_budget_config()
    store = EventStore(args.store)
    fabric = MemoryFabric(args.memory_store)
    try:
        orchestrator = Orchestrator(
            store=store,
            agent_runtime=AgentRuntime(
                _make_gateway(provider), tool_gateway=build_default_tool_gateway(fabric)
            ),
            critic=CriticService(),
            registry=registry,
            knowledge_manager=KnowledgeManager(fabric),
            approval_gateway=_make_approval_gateway(args.approval),
            pricing=budget_config.pricing,
            soft_ratio=budget_config.soft_ratio,
            max_revisions=args.max_revisions,
            artifact_dir=Path(args.artifact_dir),
        )
        spec = compile_task(args.text)
        print(f"task_id={spec.task_id}")
        if orchestra is not None:
            print(f"orchestra={orchestra.harness_id} ({len(orchestra.phases)} phases)")
            result: OrchestratorResult = await orchestrator.run_orchestra(spec, orchestra)
        else:
            topology = select_topology(spec, registry[args.harness])
            print(f"topology={topology.level.value} ({topology.reason})")
            result = await orchestrator.run_task(spec, args.harness)
        _print_result(result)
        return 0 if result.final_state.value == "completed" else 1
    finally:
        fabric.close()
        store.close()


def _print_result(result: OrchestratorResult) -> None:
    print(f"final_state={result.final_state.value}")
    if result.failure_reason:
        print(f"failure_reason={result.failure_reason}")
    print(f"supplied_assets={len(result.supplied_asset_ids)}")
    if result.reused_asset_ids:
        print(f"reused_assets={','.join(result.reused_asset_ids)}")
    for index, critique in enumerate(result.critiques):
        print(
            f"critique[{index}]: {critique.target_agent} -> {critique.status.value}"
            f" (zero_shot_detected={critique.zero_shot_detected})"
        )
    if result.artifact is not None:
        print(f"artifact_id={result.artifact.artifact_id}")
        print(f"content_hash={result.artifact.content_hash}")
    if result.artifact_path:
        print(f"artifact_path={result.artifact_path}")


def _replay(args: argparse.Namespace) -> int:
    store = EventStore(args.store)
    try:
        events = store.for_task(args.task_id)
        if not events:
            print(f"error: no events found for task '{args.task_id}'")
            return 1
        states = replay_states(events)
        print(" -> ".join(state.value for state in states))
        return 0
    finally:
        store.close()


def _metrics(args: argparse.Namespace) -> int:
    store = EventStore(args.store)
    try:
        metrics = compute_metrics(store, pricing=load_budget_config().pricing)
        for key, value in metrics.model_dump().items():
            print(f"{key}={value}")
        return 0
    finally:
        store.close()


def _eval(args: argparse.Namespace) -> int:
    registry = {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }
    report = run_golden_suite(Path(args.golden), registry)
    print(f"golden_cases={report.total} passed={report.passed} failed={len(report.failures)}")
    for failure in report.failures:
        print(
            f"REGRESSION {failure.case_id}: expected {failure.expected_status.value}"
            f"/zero_shot={failure.expected_zero_shot}, got {failure.actual_status.value}"
            f"/zero_shot={failure.actual_zero_shot}"
        )
    assert_no_regression(report)
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from headmaster.api.main import create_app

    static_dir = Path(args.static_dir)
    app = create_app(
        store=EventStore(args.store),
        fabric=MemoryFabric(args.memory_store),
        provider=args.provider,
        artifact_dir=Path(args.artifact_dir),
        static_dir=static_dir if static_dir.is_dir() else None,
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _improve(args: argparse.Namespace) -> int:
    from headmaster.assurance_plane.self_improvement import (
        analyze_failures,
        promote_patch,
        propose_patches,
    )
    from headmaster.control_plane.harness_registry import TEMPLATES_DIR

    registry = {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }
    store = EventStore(args.store)
    try:
        report = analyze_failures(store, min_count=args.min_count)
        print(f"total_rejections={report.total_rejections}")
        for pattern in report.patterns:
            print(f"pattern: {pattern.harness_id}/{pattern.issue_type} x{pattern.count}")
        patches = propose_patches(report, registry)
        if not patches:
            print("no patches proposed")
            return 0
        for patch in patches:
            print(f"proposed [{patch.patch_id}] {patch.harness_id}: {patch.rationale}")
            if not args.apply:
                continue
            written = promote_patch(patch, registry, TEMPLATES_DIR, Path(args.golden))
            if written is None:
                print("  -> BLOCKED (golden regression or already applied)")
            else:
                print(f"  -> PROMOTED {written}")
        if not args.apply:
            print("dry-run - pass --apply to promote validated patches")
        return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run(args))
    if args.command == "metrics":
        return _metrics(args)
    if args.command == "eval":
        return _eval(args)
    if args.command == "serve":
        return _serve(args)
    if args.command == "improve":
        return _improve(args)
    return _replay(args)


if __name__ == "__main__":
    sys.exit(main())
