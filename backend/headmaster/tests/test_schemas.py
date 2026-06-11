"""Phase 0 gates 0-1 ~ 0-4: schema compilation and report-example compatibility."""

import pytest
from pydantic import ValidationError

from headmaster.schemas import (
    AgentManifest,
    Claim,
    CritiqueReport,
    CritiqueStatus,
    EvidenceBundle,
    IBFProof,
    MemoryRecord,
    MemoryScope,
    SourceRef,
    TaskSpec,
    VerifierStatus,
)

# Gate 0-2: the raw v8 Critic output example must validate unmodified.
V8_CRITIC_EXAMPLE = {
    "target_agent": "@Agent_Planner",
    "status": "REJECTED",
    "zero_shot_detected": True,
    "verification_details": {
        "imitation_check": "Fail - no RAG asset referenced",
        "benchmark_check": "Pass - competitor IA patterns cited",
        "fusion_coherence": "Fail - client data not integrated",
    },
    "mandatory_revisions": ["Enforce specific I-B-F compliance here."],
}


def test_v8_critic_example_validates() -> None:
    report = CritiqueReport.model_validate(V8_CRITIC_EXAMPLE)
    assert report.status is CritiqueStatus.REJECTED
    assert report.zero_shot_detected is True
    assert report.accepted is False
    assert report.critique_id.startswith("crt_")


# Gate 0-3: TaskSpec example adapted from the 2nd report.
def test_task_spec_from_2nd_report() -> None:
    spec = TaskSpec.model_validate(
        {
            "title": "Headmaster deep research report",
            "intent": "해마 시스템 심층 연구 보고서 작성",
            "constraints": {
                "language": "ko",
                "budget": {"max_model_cost_usd": 25.0, "max_tool_calls": 400},
            },
            "risk_profile": {
                "data_sensitivity": "internal",
                "action_risk": "medium",
                "needs_human_approval": True,
            },
            "inputs": [{"type": "file", "ref": "turn0file0", "trust": "user_provided"}],
            "success_criteria": ["명세 포함", "API 포함", "상태머신 포함"],
        }
    )
    assert spec.task_id.startswith("tsk_")
    assert spec.risk_profile.needs_human_approval is True
    assert spec.constraints.budget.max_model_cost_usd == 25.0


def test_evidence_bundle_with_ibf_proof() -> None:
    bundle = EvidenceBundle(
        task_id="tsk_x",
        ibf_proof=IBFProof(
            imitated_assets=["RAG_Asset_42"],
            benchmarked_references=["https://example.com/competitor"],
            fusion_method="Mapped client facts onto the imitated skeleton.",
        ),
        claims=[
            Claim(
                claim_id="c1",
                text="Headmaster must be an agentic runtime",
                claim_type="design_inference",
                supports=[SourceRef(source="turn0file2", kind="file")],
                confidence=0.84,
            )
        ],
    )
    assert bundle.verifier_status is VerifierStatus.PENDING
    assert bundle.bundle_id.startswith("evb_")


def test_claim_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        Claim(claim_id="c1", text="x", claim_type="factual_assertion", confidence=1.5)


def test_memory_record_bounds_and_defaults() -> None:
    record = MemoryRecord(scope=MemoryScope.EPISODIC, summary="tool misselection episode")
    assert record.quarantine is False
    assert record.reuse_count == 0
    with pytest.raises(ValidationError):
        MemoryRecord(scope=MemoryScope.EPISODIC, summary="x", salience=2.0)


def test_agent_manifest_example() -> None:
    manifest = AgentManifest.model_validate(
        {
            "agent_id": "critic_v1",
            "role": "critic",
            "capabilities": ["claim_check", "schema_validation"],
            "input_schema": "EvidenceBundle",
            "output_schema": "CritiqueReport",
            "cost_tier": "mini",
            "max_concurrency": 8,
            "requires_memory_scopes": ["episodic", "evidence"],
            "policy_tags": ["no_final_publish"],
        }
    )
    assert MemoryScope.EVIDENCE in manifest.requires_memory_scopes
