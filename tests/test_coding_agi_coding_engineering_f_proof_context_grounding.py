from __future__ import annotations

import pytest

from nolane.external_core._software_engineering_property_evidence_v01 import (
    EngineeringPropertyEvidenceLedger as FrozenPropertyEvidenceLedger,
)
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)

PATCH_REF = "patch-proof-context-1"
PATCH_DIGEST = "sha256:proof-context-1"
SOURCE_REVISION = "git:f-v12"


def _obligation(ledger, claim_class, property_ref):
    return ledger.register_obligation(
        claim_id=f"claim:{property_ref}",
        claim_class=claim_class,
        property_ref=property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
    )


def _attest(evidence, obligation, kind, suffix, extra_refs=()):
    oracle_ref = f"oracle:{obligation.property_ref}"
    return evidence.record(
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        producer_agent_id="coding.backend.01",
        verifier_agent_id=f"verification.testing.{suffix}",
        verifier_region="verification-testing",
        kind=kind,
        passed=True,
        evidence_refs=(oracle_ref,) + tuple(extra_refs),
        source_revision=SOURCE_REVISION,
        environment_digest=f"env:{suffix}",
    )


def _witness(ledger, obligation, attestation, method, *, role=EngineeringWitnessRole.DIRECT, baseline=None, falsifier=None):
    return ledger.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=method,
        role=role,
        measured_property_ref=obligation.property_ref,
        oracle_ref=f"oracle:{obligation.property_ref}",
        source_family=f"family:{attestation.verifier_agent_id}",
        baseline_revision=baseline,
        falsifier_ref=falsifier,
    )


def test_baseline_must_be_bound_by_verifier_attestation() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.REGRESSION_PRESERVATION, "regression:auth")
    baseline = "git:baseline-auth"
    attestation = _attest(evidence, obligation, EngineeringEvidenceKind.TEST, "regression")
    witness = _witness(ledger, obligation, attestation, EngineeringProofMethod.REGRESSION_TEST, role=EngineeringWitnessRole.REGRESSION, baseline=baseline)

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert blocked.ready is False
    assert f"baseline_not_attested:{witness.witness_id}" in blocked.reasons

    bound_attestation = _attest(evidence, obligation, EngineeringEvidenceKind.TEST, "regression-bound", (baseline,))
    bound = _witness(ledger, obligation, bound_attestation, EngineeringProofMethod.REGRESSION_TEST, role=EngineeringWitnessRole.REGRESSION, baseline=baseline)
    assert ledger.assess(obligation.obligation_id, witness_ids=(bound.witness_id,)).ready is True


def test_falsifier_must_be_bound_by_verifier_attestation() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(ledger, EngineeringClaimClass.DEBUG_ROOT_CAUSE, "root-cause:listener")
    reproduction_attestation = _attest(evidence, obligation, EngineeringEvidenceKind.REPRODUCTION, "reproduction")
    reproduction = _witness(ledger, obligation, reproduction_attestation, EngineeringProofMethod.REPRODUCTION)
    falsifier = "probe:remove-listener-and-replay"
    causal_attestation = _attest(evidence, obligation, EngineeringEvidenceKind.ROOT_CAUSE, "causal")
    causal = _witness(ledger, obligation, causal_attestation, EngineeringProofMethod.CAUSAL_PROBE, role=EngineeringWitnessRole.FALSIFIER, falsifier=falsifier)

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(reproduction.witness_id, causal.witness_id))
    assert blocked.ready is False
    assert f"falsifier_not_attested:{causal.witness_id}" in blocked.reasons

    bound_attestation = _attest(evidence, obligation, EngineeringEvidenceKind.ROOT_CAUSE, "causal-bound", (falsifier,))
    bound = _witness(ledger, obligation, bound_attestation, EngineeringProofMethod.CAUSAL_PROBE, role=EngineeringWitnessRole.FALSIFIER, falsifier=falsifier)
    assert ledger.assess(obligation.obligation_id, witness_ids=(reproduction.witness_id, bound.witness_id)).ready is True


def test_restore_rejects_frozen_ready_snapshot_with_unattested_baseline() -> None:
    evidence = EngineeringEvidenceLedger()
    frozen = FrozenPropertyEvidenceLedger(evidence=evidence)
    obligation = _obligation(
        frozen,
        EngineeringClaimClass.PERFORMANCE_PROPERTY,
        "performance:dispatch-p95-not-regressed",
    )
    baseline = "git:performance-baseline"
    attestation = _attest(
        evidence,
        obligation,
        EngineeringEvidenceKind.PERFORMANCE,
        "performance-frozen",
    )
    witness = _witness(
        frozen,
        obligation,
        attestation,
        EngineeringProofMethod.PERFORMANCE_BENCHMARK,
        baseline=baseline,
    )
    historical = frozen.assess(
        obligation.obligation_id,
        witness_ids=(witness.witness_id,),
    )
    assert historical.ready is True

    with pytest.raises(ValueError, match="grounded|proof context|baseline"):
        EngineeringPropertyEvidenceLedger.from_state(
            evidence=evidence,
            state=frozen.to_state(),
        )
