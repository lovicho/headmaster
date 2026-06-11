"""Critic service — mechanical I-B-F proof verification (v8 Red Team gate).

Phase 1 verifies field presence and consistency mechanically (1st report:
the critic checks the existence and coherence of proof fields, not prose).
An LLM-based critique pass layers on top in a later phase.
"""

from headmaster.schemas.critique_report import (
    CritiqueReport,
    CritiqueStatus,
    Finding,
    VerificationDetails,
)
from headmaster.schemas.evidence_bundle import EvidenceBundle
from headmaster.schemas.harness_manifest import AgentHarness, IBFRequirements

ANTI_REINVENTION_ORDER = (
    "Cease invention. Imitate internal assets, benchmark external references, and fuse."
)


def requirements_for(harness: AgentHarness) -> IBFRequirements:
    """Derive proof requirements from the harness's declared I-B-F steps."""
    return IBFRequirements(
        must_reference_internal_assets=harness.ibf_protocol.imitate is not None,
        must_reference_external_benchmarks=harness.ibf_protocol.benchmark is not None,
    )


class CriticService:
    def review(
        self,
        *,
        target_agent: str,
        bundle: EvidenceBundle,
        requirements: IBFRequirements,
        task_id: str | None = None,
    ) -> CritiqueReport:
        proof = bundle.ibf_proof
        if proof is None:
            return CritiqueReport(
                task_id=task_id,
                target_agent=target_agent,
                status=CritiqueStatus.REJECTED,
                zero_shot_detected=True,
                verification_details=VerificationDetails(
                    imitation_check="Fail - no I-B-F proof attached",
                    benchmark_check="Fail - no I-B-F proof attached",
                    fusion_coherence="Fail - no I-B-F proof attached",
                ),
                findings=[
                    Finding(
                        issue_type="zero_shot_invention",
                        severity="critical",
                        description=(
                            "Deliverable was created from a blank canvas without provenance."
                        ),
                        proposed_fix=ANTI_REINVENTION_ORDER,
                    )
                ],
                mandatory_revisions=[ANTI_REINVENTION_ORDER],
                requires_replan=True,
            )

        imitation_ok = (
            not requirements.must_reference_internal_assets or bool(proof.imitated_assets)
        )
        benchmark_ok = (
            not requirements.must_reference_external_benchmarks
            or bool(proof.benchmarked_references)
        )
        fusion_ok = bool(proof.fusion_method.strip())
        zero_shot = not (proof.imitated_assets or proof.benchmarked_references)
        approved = imitation_ok and benchmark_ok and fusion_ok and not zero_shot

        findings: list[Finding] = []
        revisions: list[str] = []
        if not imitation_ok:
            findings.append(
                Finding(
                    issue_type="missing_evidence",
                    severity="critical",
                    description="No internal asset referenced although imitation is required.",
                    proposed_fix="Declare the [Mandatory_Imitation_Base] asset ids used.",
                )
            )
            revisions.append("Declare imitated internal asset ids.")
        if not benchmark_ok:
            findings.append(
                Finding(
                    issue_type="missing_evidence",
                    severity="critical",
                    description=(
                        "No external benchmark referenced although benchmarking is required."
                    ),
                    proposed_fix="Declare the benchmark reference URIs used.",
                )
            )
            revisions.append("Declare benchmarked reference URIs.")
        if not fusion_ok:
            findings.append(
                Finding(
                    issue_type="logic_gap",
                    severity="moderate",
                    description="Fusion methodology is missing or empty.",
                    proposed_fix="Explain how client-specific facts were fused into the skeleton.",
                )
            )
            revisions.append("Describe the fusion methodology.")

        def verdict(ok: bool, pass_msg: str, fail_msg: str) -> str:
            return f"Pass - {pass_msg}" if ok else f"Fail - {fail_msg}"

        return CritiqueReport(
            task_id=task_id,
            target_agent=target_agent,
            status=CritiqueStatus.APPROVED if approved else CritiqueStatus.REJECTED,
            zero_shot_detected=zero_shot,
            verification_details=VerificationDetails(
                imitation_check=verdict(
                    imitation_ok,
                    "internal assets declared" if proof.imitated_assets else "not required",
                    "imitation source missing",
                ),
                benchmark_check=verdict(
                    benchmark_ok,
                    "benchmark references declared"
                    if proof.benchmarked_references
                    else "not required",
                    "benchmark source missing",
                ),
                fusion_coherence=verdict(
                    fusion_ok, "fusion methodology declared", "fusion methodology missing"
                ),
            ),
            findings=findings,
            mandatory_revisions=revisions,
            requires_replan=not approved,
        )
