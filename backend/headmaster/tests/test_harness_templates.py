"""Phase 0 gates 0-6 ~ 0-8: v8 harness templates validate against the schema."""

from headmaster.control_plane.harness_registry import TEMPLATES_DIR, load_all
from headmaster.schemas import AgentHarness, Language, OrchestraHarness

EXPECTED_AGENT_IDS = {
    "knowledge_manager",
    "researcher",
    "consultant",
    "critic",
    "planner",
    "content",
    "design",
    "dev_fe_be",
    "secops_qa",
}
KOREAN_EDGE_AGENTS = {"consultant", "planner", "content"}


def test_all_templates_load_and_validate() -> None:
    registry = load_all(TEMPLATES_DIR)
    agents = {h.harness_id for h in registry.values() if isinstance(h, AgentHarness)}
    orchestras = {h.harness_id for h in registry.values() if isinstance(h, OrchestraHarness)}
    assert agents == EXPECTED_AGENT_IDS
    assert orchestras == {"b2b_website_v8"}


def test_english_core_everywhere() -> None:
    for harness in load_all(TEMPLATES_DIR).values():
        assert harness.language_policy.internal is Language.EN, harness.harness_id


def test_korean_edge_only_for_client_facing_agents() -> None:
    for harness in load_all(TEMPLATES_DIR).values():
        if not isinstance(harness, AgentHarness):
            continue
        expected = Language.KO if harness.harness_id in KOREAN_EDGE_AGENTS else Language.EN
        assert harness.language_policy.external is expected, harness.harness_id


def test_orchestra_gates_and_roles() -> None:
    registry = load_all(TEMPLATES_DIR)
    orchestra = registry["b2b_website_v8"]
    assert isinstance(orchestra, OrchestraHarness)
    assert set(orchestra.required_roles) == EXPECTED_AGENT_IDS
    gates = [phase.gate for phase in orchestra.phases if phase.gate is not None]
    assert len(gates) >= 5
    assert any(gate.approver == "human" for gate in gates)
    assert any(gate.approver == "critic" for gate in gates)
    assert orchestra.ibf_requirements.proof_format == [
        "asset_ids",
        "benchmark_uris",
        "trace_ids",
        "artifact_hashes",
    ]


def test_agent_roles_match_orchestra_requirements() -> None:
    registry = load_all(TEMPLATES_DIR)
    for harness in registry.values():
        if isinstance(harness, AgentHarness):
            assert harness.role == harness.harness_id
