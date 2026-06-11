"""Critic service — mechanical I-B-F proof verification (v8 Red Team gate).

Phase 1 verifies field presence and consistency mechanically (1st report:
the critic checks the existence and coherence of proof fields, not prose).
Phase 2 adds referential integrity: imitated assets must come from the
supplied [Mandatory_Imitation_Base] set, so agents cannot invent asset ids.
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
        supplied_asset_ids: set[str] | None = None,
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

        unknown_assets: list[str] = []
        if supplied_asset_ids is not None:
            unknown_assets = [
                asset for asset in proof.imitated_assets if asset not in supplied_asset_ids
            ]
        imitation_present_ok = (
            not requirements.must_reference_internal_assets or bool(proof.imitated_assets)
        )
        imitation_ok = imitation_present_ok and not unknown_assets
        benchmark_ok = (
            not requirements.must_reference_external_benchmarks
            or bool(proof.benchmarked_references)
        )
        fusion_ok = bool(proof.fusion_method.strip())
        zero_shot = not (proof.imitated_assets or proof.benchmarked_references)
        approved = imitation_ok and benchmark_ok and fusion_ok and not zero_shot

        findings: list[Finding] = []
        revisions: list[str] = []
        if unknown_assets:
            findings.append(
                Finding(
                    issue_type="missing_evidence",
                    severity="critical",
                    description=(
                        "Referenced imitation assets are not in the supplied"
                        f" [Mandatory_Imitation_Base] set: {', '.join(unknown_assets)}"
                    ),
                    proposed_fix="Reference only supplied imitation-base asset ids.",
                )
            )
            revisions.append("Reference only supplied [Mandatory_Imitation_Base] asset ids.")
        if not imitation_present_ok:
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

        if unknown_assets:
            imitation_verdict = (
                f"Fail - unknown asset reference(s): {', '.join(unknown_assets)}"
            )
        elif not imitation_present_ok:
            imitation_verdict = "Fail - imitation source missing"
        elif proof.imitated_assets:
            imitation_verdict = "Pass - internal assets declared"
        else:
            imitation_verdict = "Pass - not required"

        def verdict(ok: bool, pass_msg: str, fail_msg: str) -> str:
            return f"Pass - {pass_msg}" if ok else f"Fail - {fail_msg}"

        return CritiqueReport(
            task_id=task_id,
            target_agent=target_agent,
            status=CritiqueStatus.APPROVED if approved else CritiqueStatus.REJECTED,
            zero_shot_detected=zero_shot,
            verification_details=VerificationDetails(
                imitation_check=imitation_verdict,
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
