"""Phase 3 gate: golden-set regression blocks deployment."""

from pathlib import Path

import pytest

from headmaster.assurance_plane.evaluator import (
    EvalReport,
    RegressionError,
    assert_no_regression,
    run_golden_suite,
)
from headmaster.control_plane.harness_registry import load_all
from headmaster.schemas import AgentHarness

GOLDEN = Path(__file__).resolve().parent / "golden" / "critic_golden.json"


def _registry() -> dict[str, AgentHarness]:
    return {
        harness_id: harness
        for harness_id, harness in load_all().items()
        if isinstance(harness, AgentHarness)
    }


def test_golden_suite_passes() -> None:
    report = run_golden_suite(GOLDEN, _registry())
    assert report.total == 5
    assert report.ok, [failure.case_id for failure in report.failures]
    assert_no_regression(report)


def test_regression_is_detected_and_blocks(tmp_path: Path) -> None:
    tampered = GOLDEN.read_text("utf-8").replace(
        '"expect_status": "REJECTED",\n    "expect_zero_shot": true',
        '"expect_status": "APPROVED",\n    "expect_zero_shot": true',
        1,
    )
    golden_path = tmp_path / "tampered.json"
    golden_path.write_text(tampered, encoding="utf-8")
    report = run_golden_suite(golden_path, _registry())
    assert not report.ok
    with pytest.raises(RegressionError):
        assert_no_regression(report)


def test_empty_report_is_ok() -> None:
    assert EvalReport(total=0, passed=0).ok is True
