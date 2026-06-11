"""Headmaster CLI.

    headmaster run "<task text>" [--harness content] [--provider fake] ...
    headmaster replay <task_id> [--store PATH]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from headmaster.assurance_plane.critic_service import CriticService
from headmaster.control_plane.harness_registry import load_all
from headmaster.control_plane.task_compiler import compile_task
from headmaster.execution_plane.agent_runtime import AgentRuntime
from headmaster.execution_plane.models import (
    AnthropicAdapter,
    FakeAdapter,
    ModelAdapter,
    ModelGateway,
    OpenAIAdapter,
    load_routing,
)
from headmaster.execution_plane.orchestrator import Orchestrator, OrchestratorResult
from headmaster.schemas.harness_manifest import AgentHarness
from headmaster.storage.event_store import EventStore
from headmaster.storage.replay import replay_states

_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headmaster")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one task through the orchestrator")
    run.add_argument("text", help="task description (natural language)")
    run.add_argument("--harness", default="content", help="agent harness id (default: content)")
    run.add_argument(
        "--provider",
        default=None,
        choices=["anthropic", "openai", "fake"],
        help="override the model provider (fake = offline demo)",
    )
    run.add_argument("--store", default="./data/events.sqlite3", help="event store path")
    run.add_argument("--artifact-dir", default="./data/artifacts", help="artifact output dir")
    run.add_argument("--max-revisions", type=int, default=2)

    replay = sub.add_parser("replay", help="replay the state sequence of a task")
    replay.add_argument("task_id")
    replay.add_argument("--store", default="./data/events.sqlite3", help="event store path")
    return parser


def _make_gateway(provider_override: str | None) -> ModelGateway:
    routing = load_routing()
    adapters: dict[str, ModelAdapter] = {
        "anthropic": AnthropicAdapter(),
        "openai": OpenAIAdapter(),
        "fake": FakeAdapter(),
    }
    return ModelGateway(routing, adapters, provider_override=provider_override)


async def _run(args: argparse.Namespace) -> int:
    provider: str | None = args.provider
    if provider in _KEY_ENV and not os.environ.get(_KEY_ENV[provider]):
        print(f"error: {_KEY_ENV[provider]} is not set (or use --provider fake)")
        return 1
    registry = {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }
    if args.harness not in registry:
        print(f"error: unknown harness '{args.harness}' (available: {sorted(registry)})")
        return 1

    store = EventStore(args.store)
    try:
        orchestrator = Orchestrator(
            store=store,
            agent_runtime=AgentRuntime(_make_gateway(provider)),
            critic=CriticService(),
            registry=registry,
            max_revisions=args.max_revisions,
            artifact_dir=Path(args.artifact_dir),
        )
        spec = compile_task(args.text)
        print(f"task_id={spec.task_id}")
        result: OrchestratorResult = await orchestrator.run_task(spec, args.harness)
        _print_result(result)
        return 0 if result.final_state.value == "completed" else 1
    finally:
        store.close()


def _print_result(result: OrchestratorResult) -> None:
    print(f"final_state={result.final_state.value}")
    for index, critique in enumerate(result.critiques):
        print(
            f"critique[{index}]: {critique.status.value}"
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run(args))
    return _replay(args)


if __name__ == "__main__":
    sys.exit(main())
