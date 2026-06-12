"""Structured rejection taxonomy for Critic findings."""

from enum import StrEnum

from pydantic import BaseModel


class RejectionCategory(StrEnum):
    PROVENANCE = "provenance"
    EVIDENCE_INTEGRITY = "evidence_integrity"
    REASONING_INTEGRITY = "reasoning_integrity"
    OUTPUT_CONTRACT = "output_contract"
    POLICY = "policy"


class RejectionCode(StrEnum):
    BLANK_CANVAS_NO_PROOF = "HM-ZS-001"
    IMITATION_SOURCE_MISSING = "HM-EV-001"
    UNKNOWN_IMITATION_ASSET = "HM-EV-002"
    BENCHMARK_SOURCE_MISSING = "HM-EV-003"
    FUSION_METHOD_MISSING = "HM-LG-001"
    OUTPUT_CONTRACT_MISMATCH = "HM-FM-001"
    POLICY_DENIED = "HM-PL-001"


class RejectionDefinition(BaseModel):
    code: RejectionCode
    category: RejectionCategory
    issue_type: str
    severity: str
    title: str
    operator_summary: str
    default_fix: str
    retryable: bool = True
    requires_human_approval: bool = False


REJECTION_TAXONOMY: dict[RejectionCode, RejectionDefinition] = {
    RejectionCode.BLANK_CANVAS_NO_PROOF: RejectionDefinition(
        code=RejectionCode.BLANK_CANVAS_NO_PROOF,
        category=RejectionCategory.PROVENANCE,
        issue_type="zero_shot_invention",
        severity="critical",
        title="Blank-canvas output without I-B-F proof",
        operator_summary="The deliverable has no attached provenance proof.",
        default_fix=(
            "Attach an I-B-F proof that declares imitation assets, benchmark"
            " references, and a fusion method."
        ),
    ),
    RejectionCode.IMITATION_SOURCE_MISSING: RejectionDefinition(
        code=RejectionCode.IMITATION_SOURCE_MISSING,
        category=RejectionCategory.PROVENANCE,
        issue_type="missing_evidence",
        severity="critical",
        title="Required internal imitation source missing",
        operator_summary="The harness requires imitation but no internal asset was declared.",
        default_fix="Declare the [Mandatory_Imitation_Base] asset ids used.",
    ),
    RejectionCode.UNKNOWN_IMITATION_ASSET: RejectionDefinition(
        code=RejectionCode.UNKNOWN_IMITATION_ASSET,
        category=RejectionCategory.EVIDENCE_INTEGRITY,
        issue_type="missing_evidence",
        severity="critical",
        title="Unknown imitation asset reference",
        operator_summary="The proof references an internal asset that was not supplied.",
        default_fix="Reference only supplied imitation-base asset ids.",
    ),
    RejectionCode.BENCHMARK_SOURCE_MISSING: RejectionDefinition(
        code=RejectionCode.BENCHMARK_SOURCE_MISSING,
        category=RejectionCategory.PROVENANCE,
        issue_type="missing_evidence",
        severity="critical",
        title="Required benchmark source missing",
        operator_summary="The harness requires benchmarking but no benchmark URI was declared.",
        default_fix="Declare the benchmark reference URIs used.",
    ),
    RejectionCode.FUSION_METHOD_MISSING: RejectionDefinition(
        code=RejectionCode.FUSION_METHOD_MISSING,
        category=RejectionCategory.REASONING_INTEGRITY,
        issue_type="logic_gap",
        severity="moderate",
        title="Fusion methodology missing",
        operator_summary="The proof does not explain how sources were fused.",
        default_fix="Explain how client-specific facts were fused into the skeleton.",
    ),
    RejectionCode.OUTPUT_CONTRACT_MISMATCH: RejectionDefinition(
        code=RejectionCode.OUTPUT_CONTRACT_MISMATCH,
        category=RejectionCategory.OUTPUT_CONTRACT,
        issue_type="format_error",
        severity="critical",
        title="Output contract mismatch",
        operator_summary="The deliverable does not match the declared output contract.",
        default_fix="Rewrite the output to match the declared schema and format.",
    ),
    RejectionCode.POLICY_DENIED: RejectionDefinition(
        code=RejectionCode.POLICY_DENIED,
        category=RejectionCategory.POLICY,
        issue_type="policy_violation",
        severity="critical",
        title="Policy denied",
        operator_summary="A policy check blocked the requested action.",
        default_fix="Stay within the tool allowlist or request explicit human approval.",
        retryable=False,
        requires_human_approval=True,
    ),
}


def rejection_definition(code: RejectionCode) -> RejectionDefinition:
    """Return the taxonomy definition for a rejection code."""

    return REJECTION_TAXONOMY[code]
