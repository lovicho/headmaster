"""Rejection taxonomy contract tests."""

from headmaster.schemas import REJECTION_TAXONOMY, RejectionCode, rejection_definition


def test_rejection_taxonomy_has_unique_codes() -> None:
    values = [code.value for code in REJECTION_TAXONOMY]
    assert len(values) == len(set(values))


def test_rejection_definition_contains_operator_guidance() -> None:
    definition = rejection_definition(RejectionCode.UNKNOWN_IMITATION_ASSET)

    assert definition.code is RejectionCode.UNKNOWN_IMITATION_ASSET
    assert definition.category == "evidence_integrity"
    assert definition.issue_type == "missing_evidence"
    assert definition.default_fix
    assert definition.operator_summary
