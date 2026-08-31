from __future__ import annotations

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


PATCH_REF = "patch-source-family-1"
PATCH_DIGEST = "sha256:patch-source-family-1"
SOURCE_REVISION = "git:source-family-v1"


def _attest(
    evidence: EngineeringEvidenceLedger,
    *,
    suffix: str,
    oracle_ref: str,
    source_family: str | None = None,
):
    refs = [f"run:{suffix}", oracle_ref]
    if source_family is not None:
        refs.append(source_family)
    return evidence.record(
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        producer_agent_id="coding.backend.01",
        verifier_agent_id=f"verification.testing.{suffix}",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.SECURITY,
        passed=True,
        evidence_refs=tuple(refs),
        source_revision=SOURCE_REVISION,
        environment_digest="env:shared-security-scanner",
    )


def _witness(
    ledger: EngineeringPropertyEvidenceLedger,
    *,
    obligation_id: str,
    attestation_id: str,
    property_ref: str,
    oracle_ref: str,
    source_family: str,
):
    return ledger.record_witness(
        obligation_id=obligation_id,
        attestation_id=attestation_id,
        method=EngineeringProofMethod.SECURITY_TEST,
        role=EngineeringWitnessRole.ADVERSARIAL,
        measured_property_ref=property_ref,
        oracle_ref=oracle_ref,
        source_family=source_family,
        adversarial=True,
    )


def test_self_declared_source_families_cannot_manufacture_independence() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    property_ref = "security:no-cross-tenant-read"
    oracle_ref = f"oracle:{property_ref}"
    obligation = ledger.register_obligation(
        claim_id="claim:security:no-cross-tenant-read",
        claim_class=EngineeringClaimClass.SECURITY_PROPERTY,
        property_ref=property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        min_independent_sources=2,
    )

    # Both attestations bind the property oracle, but neither verifier attests
    # the caller-supplied lineage-family label used to claim independence.
    a = _attest(evidence, suffix="a", oracle_ref=oracle_ref)
    b = _attest(evidence, suffix="b", oracle_ref=oracle_ref)
    wa = _witness(
        ledger,
        obligation_id=obligation.obligation_id,
        attestation_id=a.attestation_id,
        property_ref=property_ref,
        oracle_ref=oracle_ref,
        source_family="family:claimed-independent-a",
    )
    wb = _witness(
        ledger,
        obligation_id=obligation.obligation_id,
        attestation_id=b.attestation_id,
        property_ref=property_ref,
        oracle_ref=oracle_ref,
        source_family="family:claimed-independent-b",
    )

    blocked = ledger.assess(
        obligation.obligation_id,
        witness_ids=(wa.witness_id, wb.witness_id),
    )
    assert blocked.ready is False
    assert any(reason.startswith("source_family_not_attested:") for reason in blocked.reasons)


def test_verifier_attested_distinct_source_families_can_satisfy_independence() -> None:
    evidence = EngineeringEvidenceLedger()
    ledger = EngineeringPropertyEvidenceLedger(evidence=evidence)
    property_ref = "security:no-cross-tenant-read"
    oracle_ref = f"oracle:{property_ref}"
    obligation = ledger.register_obligation(
        claim_id="claim:security:no-cross-tenant-read",
        claim_class=EngineeringClaimClass.SECURITY_PROPERTY,
        property_ref=property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        min_independent_sources=2,
    )

    family_a = "family:penetration-harness-a"
    family_b = "family:penetration-harness-b"
    a = _attest(evidence, suffix="a", oracle_ref=oracle_ref, source_family=family_a)
    b = _attest(evidence, suffix="b", oracle_ref=oracle_ref, source_family=family_b)
    wa = _witness(
        ledger,
        obligation_id=obligation.obligation_id,
        attestation_id=a.attestation_id,
        property_ref=property_ref,
        oracle_ref=oracle_ref,
        source_family=family_a,
    )
    wb = _witness(
        ledger,
        obligation_id=obligation.obligation_id,
        attestation_id=b.attestation_id,
        property_ref=property_ref,
        oracle_ref=oracle_ref,
        source_family=family_b,
    )

    assert ledger.assess(
        obligation.obligation_id,
        witness_ids=(wa.witness_id, wb.witness_id),
    ).ready is True
