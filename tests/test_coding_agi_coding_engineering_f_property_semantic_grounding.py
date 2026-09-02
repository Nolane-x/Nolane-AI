from __future__ import annotations

import pytest

from nolane.external_core._software_engineering_property_evidence_v01 import (
    EngineeringPropertyEvidenceLedger as LegacyPropertyEvidenceLedger,
)
from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
)
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)


SUBJECT_REF = "patch:semantic-grounding"
SUBJECT_DIGEST = "sha256:semantic-grounding"
SOURCE_REVISION = "source:semantic-grounding"
PROPERTY_REF = "property:semantic-grounding"
ORACLE_REF = "oracle:semantic-grounding"


def _evidence(
    ledger: EngineeringEvidenceLedger,
    *,
    kind: EngineeringEvidenceKind,
    refs: tuple[str, ...],
    suffix: str,
):
    return ledger.record(
        subject_ref=SUBJECT_REF,
        subject_digest=SUBJECT_DIGEST,
        producer_agent_id="coding.agent",
        verifier_agent_id=f"verification.{suffix}",
        verifier_region="verification-testing",
        kind=kind,
        passed=True,
        evidence_refs=refs,
        source_revision=SOURCE_REVISION,
        environment_digest=f"env:{suffix}",
    )


def _obligation(
    ledger: EngineeringPropertyEvidenceLedger | LegacyPropertyEvidenceLedger,
    claim_class: EngineeringClaimClass,
):
    return ledger.register_obligation(
        claim_id=f"claim:{claim_class.value}",
        claim_class=claim_class,
        property_ref=PROPERTY_REF,
        subject_ref=SUBJECT_REF,
        subject_digest=SUBJECT_DIGEST,
        source_revision=SOURCE_REVISION,
    )


def _record(
    ledger: EngineeringPropertyEvidenceLedger | LegacyPropertyEvidenceLedger,
    obligation_id: str,
    attestation_id: str,
    *,
    method: EngineeringProofMethod,
    role: EngineeringWitnessRole = EngineeringWitnessRole.DIRECT,
    baseline_revision: str | None = None,
    falsifier_ref: str | None = None,
    adversarial: bool = False,
):
    return ledger.record_witness(
        obligation_id=obligation_id,
        attestation_id=attestation_id,
        method=method,
        role=role,
        measured_property_ref=PROPERTY_REF,
        oracle_ref=ORACLE_REF,
        source_family="source-family:semantic-grounding",
        baseline_revision=baseline_revision,
        falsifier_ref=falsifier_ref,
        adversarial=adversarial,
    )


def test_generic_test_attestation_cannot_be_labeled_property_test_by_caller() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        refs=(ORACLE_REF,),
        suffix="generic-test",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.FUNCTIONAL_BEHAVIOR)

    with pytest.raises(ValueError, match="proof method.*attested|proof-method"):
        _record(
            ledger,
            obligation.obligation_id,
            attestation.attestation_id,
            method=EngineeringProofMethod.PROPERTY_TEST,
        )


def test_mismatched_attested_proof_method_cannot_be_reinterpreted_by_caller() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        refs=(ORACLE_REF, "proof-method:unit_test"),
        suffix="method-mismatch",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.FUNCTIONAL_BEHAVIOR)

    with pytest.raises(ValueError, match="proof method.*attested|proof-method"):
        _record(
            ledger,
            obligation.obligation_id,
            attestation.attestation_id,
            method=EngineeringProofMethod.PROPERTY_TEST,
        )


def test_baseline_revision_must_be_bound_by_verifier_attestation() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        refs=(ORACLE_REF, "proof-method:regression_test"),
        suffix="baseline",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.REGRESSION_PRESERVATION)

    with pytest.raises(ValueError, match="baseline.*attested|baseline-revision"):
        _record(
            ledger,
            obligation.obligation_id,
            attestation.attestation_id,
            method=EngineeringProofMethod.REGRESSION_TEST,
            baseline_revision="baseline:v1",
        )


def test_falsifier_role_and_reference_must_be_verifier_grounded() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.ROOT_CAUSE,
        refs=(ORACLE_REF, "proof-method:causal_probe"),
        suffix="falsifier",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.DEBUG_ROOT_CAUSE)

    with pytest.raises(ValueError, match="witness role.*attested|falsifier.*attested|witness-role|falsifier-ref"):
        _record(
            ledger,
            obligation.obligation_id,
            attestation.attestation_id,
            method=EngineeringProofMethod.CAUSAL_PROBE,
            role=EngineeringWitnessRole.FALSIFIER,
            falsifier_ref="falsifier:counterexample-1",
        )


def test_adversarial_flag_cannot_be_manufactured_by_caller() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.SECURITY,
        refs=(ORACLE_REF, "proof-method:security_test"),
        suffix="adversarial",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.SECURITY_PROPERTY)

    with pytest.raises(ValueError, match="adversarial.*attested|adversarial:true"):
        _record(
            ledger,
            obligation.obligation_id,
            attestation.attestation_id,
            method=EngineeringProofMethod.SECURITY_TEST,
            adversarial=True,
        )


def test_exact_verifier_semantic_markers_support_property_closure() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        refs=(
            ORACLE_REF,
            "proof-method:regression_test",
            "baseline-revision:baseline:v1",
        ),
        suffix="positive-regression",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.REGRESSION_PRESERVATION)
    witness = _record(
        ledger,
        obligation.obligation_id,
        attestation.attestation_id,
        method=EngineeringProofMethod.REGRESSION_TEST,
        baseline_revision="baseline:v1",
    )

    closure = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))

    assert closure.ready is True
    assert closure.authority == "candidate_only"


def test_exact_adversarial_role_marker_supports_security_closure() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.SECURITY,
        refs=(
            ORACLE_REF,
            "proof-method:security_test",
            "witness-role:adversarial",
        ),
        suffix="positive-security",
    )
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.SECURITY_PROPERTY)
    witness = _record(
        ledger,
        obligation.obligation_id,
        attestation.attestation_id,
        method=EngineeringProofMethod.SECURITY_TEST,
        role=EngineeringWitnessRole.ADVERSARIAL,
    )

    closure = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))

    assert closure.ready is True
    assert closure.authority == "candidate_only"


def test_restore_rejects_historical_ready_receipt_built_from_ungrounded_method_label() -> None:
    evidence = EngineeringEvidenceLedger()
    attestation = _evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        refs=(ORACLE_REF,),
        suffix="restore-laundering",
    )
    legacy = LegacyPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(legacy, EngineeringClaimClass.FUNCTIONAL_BEHAVIOR)
    witness = _record(
        legacy,
        obligation.obligation_id,
        attestation.attestation_id,
        method=EngineeringProofMethod.PROPERTY_TEST,
    )
    closure = legacy.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert closure.ready is True

    with pytest.raises(ValueError, match="semantic.*ground|proof method.*attested|proof-method"):
        EngineeringPropertyEvidenceLedger.from_state(
            evidence=evidence,
            state=legacy.to_state(),
        )
