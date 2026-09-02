from __future__ import annotations

from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)


def _attestation(evidence: EngineeringEvidenceLedger, *, oracle_ref: str | None):
    refs = ["run:functional-contract", "proof-method:integration_test"]
    if oracle_ref is not None:
        refs.append(oracle_ref)
    return evidence.record(
        subject_ref="patch-oracle-1",
        subject_digest="sha256:patch-oracle-1",
        producer_agent_id="coding.backend.01",
        verifier_agent_id="verification.testing.oracle",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.TEST,
        passed=True,
        evidence_refs=tuple(refs),
        source_revision="git:oracle-v1",
        environment_digest="env:oracle-v1",
    )


def _obligation(ledger: EngineeringPropertyEvidenceLedger):
    return ledger.register_obligation(
        claim_id="claim:functional:refresh",
        claim_class=EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        property_ref="behavior:refresh-preserves-session",
        subject_ref="patch-oracle-1",
        subject_digest="sha256:patch-oracle-1",
        source_revision="git:oracle-v1",
    )


def test_self_declared_property_label_cannot_upgrade_unbound_green_test() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger)
    attestation = _attestation(evidence, oracle_ref=None)
    witness = ledger.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=EngineeringProofMethod.INTEGRATION_TEST,
        role=EngineeringWitnessRole.DIRECT,
        measured_property_ref=obligation.property_ref,
        oracle_ref="oracle:refresh-session-contract",
        source_family="independent:integration-runner",
    )

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert blocked.ready is False
    assert f"oracle_not_attested:{witness.witness_id}" in blocked.reasons


def test_verifier_attested_oracle_can_close_exact_property() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger)
    oracle_ref = "oracle:refresh-session-contract"
    attestation = _attestation(evidence, oracle_ref=oracle_ref)
    witness = ledger.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=EngineeringProofMethod.INTEGRATION_TEST,
        role=EngineeringWitnessRole.DIRECT,
        measured_property_ref=obligation.property_ref,
        oracle_ref=oracle_ref,
        source_family="independent:integration-runner",
    )

    assert ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,)).ready is True
