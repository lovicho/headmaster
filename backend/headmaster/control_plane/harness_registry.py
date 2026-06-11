"""Harness registry — loads and validates versioned harness manifests (YAML).

Phase 0 scope: load + validate. Selection/version-pinning arrives in Phase 1.
"""

from pathlib import Path

import yaml

from headmaster.schemas.harness_manifest import AgentHarness, OrchestraHarness, harness_adapter

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "harnesses"


def load_harness(path: Path) -> AgentHarness | OrchestraHarness:
    """Load a single harness manifest and validate it against the schema."""
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return harness_adapter.validate_python(raw)


def load_all(directory: Path = TEMPLATES_DIR) -> dict[str, AgentHarness | OrchestraHarness]:
    """Load every ``*.yaml`` harness under *directory* (recursive), keyed by harness_id."""
    registry: dict[str, AgentHarness | OrchestraHarness] = {}
    for path in sorted(directory.rglob("*.yaml")):
        harness = load_harness(path)
        if harness.harness_id in registry:
            raise ValueError(f"duplicate harness_id: {harness.harness_id} ({path})")
        registry[harness.harness_id] = harness
    return registry
