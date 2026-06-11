"""Eval runner — golden-set regression for the critic pipeline.

A golden case feeds a canned model response through the same parse->bundle->
critic path used in production and pins the expected verdict. Any mismatch
is a regression and must block deployment (plan/03 Phase 3 gate).
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from headmaster.assurance_plane.critic_service import CriticService, requirements_for
from headmaster.execution_plane.agent_runtime import extract_json_object
from headmaster.schemas.critique_report import CritiqueStatus
from headmaster.schemas.evidence_bundle import EvidenceBundle, IBFProof
from headmaster.schemas.harness_manifest import AgentHarness


class GoldenCase(BaseModel):
    id: str
    harness: str
    response: str
    expect_status: CritiqueStatus
    expect_zero_shot: bool


class EvalFailure(BaseModel):
    case_id: str
    expected_status: CritiqueStatus
    actual_status: CritiqueStatus
    expected_zero_shot: bool
    actual_zero_shot: bool


class EvalReport(BaseModel):
    total: int
    passed: int
    failures: list[EvalFailure] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


class RegressionError(Exception):
    def __init__(self, report: EvalReport) -> None:
        failed = ", ".join(failure.case_id for failure in report.failures)
        super().__init__(f"golden-set regression: {len(report.failures)} case(s) failed ({failed})")
        self.report = report


def _bundle_from_response(response: str) -> EvidenceBundle:
    """Replicates the production parse path (agent_runtime) for a canned response."""
    parsed = extract_json_object(response)
    proof: IBFProof | None = None
    if parsed is not None and parsed.get("ibf_proof") is not None:
        try:
            proof = IBFProof.model_validate(parsed["ibf_proof"])
        except ValidationError:
            proof = None
    return EvidenceBundle(task_id="tsk_golden", ibf_proof=proof)


def run_golden_suite(
    path: Path, registry: dict[str, AgentHarness], critic: CriticService | None = None
) -> EvalReport:
    critic = critic or CriticService()
    cases = [GoldenCase.model_validate(raw) for raw in json.loads(path.read_text("utf-8"))]
    failures: list[EvalFailure] = []
    for case in cases:
        harness = registry[case.harness]
        report = critic.review(
            target_agent=case.harness,
            bundle=_bundle_from_response(case.response),
            requirements=requirements_for(harness),
        )
        if report.status is not case.expect_status or (
            report.zero_shot_detected is not case.expect_zero_shot
        ):
            failures.append(
                EvalFailure(
                    case_id=case.id,
                    expected_status=case.expect_status,
                    actual_status=report.status,
                    expected_zero_shot=case.expect_zero_shot,
                    actual_zero_shot=report.zero_shot_detected,
                )
            )
    return EvalReport(total=len(cases), passed=len(cases) - len(failures), failures=failures)


def assert_no_regression(report: EvalReport) -> None:
    """Deployment gate: raise on any golden-set mismatch."""
    if not report.ok:
        raise RegressionError(report)
