"""Phase 1 gate 1-2: deliverables without I-B-F proof are auto-rejected."""

from headmaster.assurance_plane.critic_service import (
    ANTI_REINVENTION_ORDER,
    CriticService,
    requirements_for,
)
from headmaster.control_plane.harness_registry import load_all
from headmaster.schemas import (
    AgentHarness,
    CritiqueStatus,
    EvidenceBundle,
    IBFProof,
    IBFRequirements,
    RejectionCode,
)

CRITIC = CriticService()
FULL_REQUIREMENTS = IBFRequirements()


def _bundle(proof: IBFProof | None) -> EvidenceBundle:
    return EvidenceBundle(task_id="tsk_test", ibf_proof=proof)


def test_missing_proof_rejected_as_zero_shot() -> None:
    report = CRITIC.review(
        target_agent="content",
        bundle=_bundle(None),
        requirements=FULL_REQUIREMENTS,
        task_id="tsk_test",
    )
    assert report.status is CritiqueStatus.REJECTED
    assert report.zero_shot_detected is True
    assert report.findings[0].code is RejectionCode.BLANK_CANVAS_NO_PROOF
    assert report.findings[0].category == "provenance"
    assert report.requires_replan is True
    assert ANTI_REINVENTION_ORDER in report.mandatory_revisions


def test_missing_imitation_rejected_when_required() -> None:
    proof = IBFProof(
        imitated_assets=[],
        benchmarked_references=["https://example.com"],
        fusion_method="Fused benchmark patterns with client facts.",
    )
    report = CRITIC.review(
        target_agent="content", bundle=_bundle(proof), requirements=FULL_REQUIREMENTS
    )
    assert report.status is CritiqueStatus.REJECTED
    assert report.verification_details.imitation_check.startswith("Fail")
    assert report.zero_shot_detected is False
    assert {finding.code for finding in report.findings} == {
        RejectionCode.IMITATION_SOURCE_MISSING
    }


def test_valid_proof_approved() -> None:
    proof = IBFProof(
        imitated_assets=["asset_1"],
        benchmarked_references=["https://example.com"],
        fusion_method="Mapped client facts onto the imitated skeleton.",
    )
    report = CRITIC.review(
        target_agent="content", bundle=_bundle(proof), requirements=FULL_REQUIREMENTS
    )
    assert report.status is CritiqueStatus.APPROVED
    assert report.accepted is True
    assert report.findings == []


def test_unknown_asset_rejected_even_when_imitation_optional() -> None:
    proof = IBFProof(
        imitated_assets=["made_up_internal_asset"],
        benchmarked_references=["https://example.com"],
        fusion_method="Mapped client facts onto the benchmark pattern.",
    )
    report = CRITIC.review(
        target_agent="content",
        bundle=_bundle(proof),
        requirements=IBFRequirements(
            must_reference_internal_assets=False,
            must_reference_external_benchmarks=True,
        ),
        supplied_asset_ids=set(),
    )
    assert report.status is CritiqueStatus.REJECTED
    assert report.verification_details.imitation_check.startswith("Fail")
    assert report.findings[0].code is RejectionCode.UNKNOWN_IMITATION_ASSET
    assert report.findings[0].category == "evidence_integrity"


def test_requirements_derived_from_harness_protocol() -> None:
    registry = load_all()
    researcher = registry["researcher"]
    assert isinstance(researcher, AgentHarness)
    requirements = requirements_for(researcher)
    # researcher declares only a Benchmark step -> imitation not required
    assert requirements.must_reference_internal_assets is False
    assert requirements.must_reference_external_benchmarks is True

    content = registry["content"]
    assert isinstance(content, AgentHarness)
    full = requirements_for(content)
    assert full.must_reference_internal_assets is True
    assert full.must_reference_external_benchmarks is True
