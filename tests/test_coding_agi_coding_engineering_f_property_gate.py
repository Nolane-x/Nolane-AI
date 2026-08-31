from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyRequirement,
    SoftwareEngineeringPropertyGate,
)


PATCH_REF = "patch-property-gate-0001"
PATCH_DIGEST = "sha256:patch-property-gate-0001"
SOURCE_REVISION = "git:property-gate-v1"


@dataclass(frozen=True)
class _BaseClosure:
    receipt_id: str
    digest: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    ready: bool


def _systems():
    evidence = EngineeringEvidenceLedger()
    properties = EngineeringPropertyEvidenceLedger(evidence=evidence)
    gate = SoftwareEngineeringPropertyGate(property_evidence=properties)
    return evidence, properties, gate


def _requirement(claim_class: EngineeringClaimClass, property_ref: str) -> EngineeringPropertyRequirement:
    return EngineeringPropertyRequirement(
        claim_id=f"claim:{claim_class.value}:{property_ref}",
        claim_class=claim_class,
        property_ref=property_ref,
    )


def _manifest(gate: SoftwareEngineeringPropertyGate, *requirements: EngineeringPropertyRequirement):
    return gate.register_manifest(
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        source_authority_ref="goal-design:decision-receipt-v3:engineering-contract",
        requirements=tuple(requirements),
    )


def _closure(
    evidence: EngineeringEvidenceLedger,
    properties: EngineeringPropertyEvidenceLedger,
    requirement: EngineeringPropertyRequirement,
    *,
    kind: EngineeringEvidenceKind,
    method: EngineeringProofMethod,
    suffix: str,
    role: EngineeringWitnessRole = EngineeringWitnessRole.DIRECT,
    baseline_revision: str | None = None,
    falsifier_ref: str | None = None,
    adversarial: bool = False,
):
    obligation = properties.register_obligation(
        claim_id=requirement.claim_id,
        claim_class=requirement.claim_class,
        property_ref=requirement.property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
    )
    oracle_ref = f"oracle:{requirement.property_ref}"
    attestation = evidence.record(
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        producer_agent_id="coding.backend.01",
        verifier_agent_id=f"verification.testing.{suffix}",
        verifier_region="verification-testing",
        kind=kind,
        passed=True,
        evidence_refs=(f"run:{suffix}", oracle_ref),
        source_revision=SOURCE_REVISION,
        environment_digest=f"env:{suffix}",
    )
    witness = properties.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=method,
        role=role,
        measured_property_ref=requirement.property_ref,
        oracle_ref=oracle_ref,
        source_family=f"independent:{suffix}",
        baseline_revision=baseline_revision,
        falsifier_ref=falsifier_ref,
        adversarial=adversarial,
    )
    closure = properties.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert closure.ready is True
    return obligation, witness, closure


def test_manifest_is_complete_set_gate_not_any_one_green_property() -> None:
    evidence, properties, gate = _systems()
    functional = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:session-refresh",
    )
    regression = _requirement(
        EngineeringClaimClass.REGRESSION_PRESERVATION,
        "regression:existing-session-contracts",
    )
    manifest = _manifest(gate, functional, regression)
    functional_obligation, _, functional_closure = _closure(
        evidence,
        properties,
        functional,
        kind=EngineeringEvidenceKind.TEST,
        method=EngineeringProofMethod.INTEGRATION_TEST,
        suffix="functional",
    )

    receipt = gate.assess(
        manifest.manifest_id,
        property_bindings=((functional_obligation.obligation_id, functional_closure.receipt_id),),
    )
    assert receipt.ready is False
    assert any(reason.startswith("missing_required_property:") for reason in receipt.reasons)
    assert receipt.authority == "candidate_only"


def test_wrong_claim_class_or_property_cannot_substitute_for_manifest_requirement() -> None:
    evidence, properties, gate = _systems()
    required = _requirement(
        EngineeringClaimClass.UI_INTERACTION,
        "ui:composer-submit-flow",
    )
    manifest = _manifest(gate, required)
    visual = _requirement(
        EngineeringClaimClass.UI_VISUAL_FIDELITY,
        "ui:composer-submit-flow",
    )
    obligation, _, closure = _closure(
        evidence,
        properties,
        visual,
        kind=EngineeringEvidenceKind.VISUAL,
        method=EngineeringProofMethod.VISUAL_DIFF,
        suffix="visual",
    )

    receipt = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, closure.receipt_id),),
    )
    assert receipt.ready is False
    assert any(reason.startswith("unexpected_or_mismatched_property:") for reason in receipt.reasons)
    assert any(reason.startswith("missing_required_property:") for reason in receipt.reasons)


def test_gate_recomputes_historical_green_closure_after_evidence_revocation() -> None:
    evidence, properties, gate = _systems()
    required = _requirement(
        EngineeringClaimClass.BUILD_INTEGRITY,
        "build:canonical-package-compiles",
    )
    manifest = _manifest(gate, required)
    obligation, witness, historical_green = _closure(
        evidence,
        properties,
        required,
        kind=EngineeringEvidenceKind.COMPILE,
        method=EngineeringProofMethod.COMPILE,
        suffix="compile",
    )
    first = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, historical_green.receipt_id),),
    )
    assert first.ready is True

    evidence.revoke(witness.attestation_id, reason="compiler provenance invalidated")
    reopened = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, historical_green.receipt_id),),
    )
    assert reopened.ready is False
    assert any(reason.startswith("property_not_currently_closed:") for reason in reopened.reasons)


def test_property_bound_terminal_closure_requires_both_legacy_and_property_gate() -> None:
    evidence, properties, gate = _systems()
    required = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:refresh-preserves-session",
    )
    manifest = _manifest(gate, required)
    obligation, _, property_closure = _closure(
        evidence,
        properties,
        required,
        kind=EngineeringEvidenceKind.TEST,
        method=EngineeringProofMethod.PROPERTY_TEST,
        suffix="property",
    )
    property_gate = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, property_closure.receipt_id),),
    )
    assert property_gate.ready is True

    legacy_ready = _BaseClosure(
        receipt_id="eng-closure-legacy-ready",
        digest="sha256:legacy-ready",
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        ready=True,
    )
    bound = gate.bind_terminal_closure(
        base_closure=legacy_ready,
        property_gate_receipt_id=property_gate.receipt_id,
    )
    assert bound.ready is True
    assert bound.authority == "candidate_only"

    legacy_blocked = _BaseClosure(
        receipt_id="eng-closure-legacy-blocked",
        digest="sha256:legacy-blocked",
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        ready=False,
    )
    blocked = gate.bind_terminal_closure(
        base_closure=legacy_blocked,
        property_gate_receipt_id=property_gate.receipt_id,
    )
    assert blocked.ready is False
    assert "base_engineering_closure_not_ready" in blocked.reasons


def test_terminal_binding_rejects_cross_patch_or_revision_reuse() -> None:
    evidence, properties, gate = _systems()
    required = _requirement(
        EngineeringClaimClass.BUILD_INTEGRITY,
        "build:package-compiles",
    )
    manifest = _manifest(gate, required)
    obligation, _, closure = _closure(
        evidence,
        properties,
        required,
        kind=EngineeringEvidenceKind.COMPILE,
        method=EngineeringProofMethod.COMPILE,
        suffix="compile-lineage",
    )
    property_gate = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, closure.receipt_id),),
    )
    stale_base = _BaseClosure(
        receipt_id="eng-closure-stale",
        digest="sha256:legacy-stale",
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision="git:older-revision",
        ready=True,
    )
    bound = gate.bind_terminal_closure(
        base_closure=stale_base,
        property_gate_receipt_id=property_gate.receipt_id,
    )
    assert bound.ready is False
    assert "base_property_revision_mismatch" in bound.reasons


def test_gate_snapshot_rejects_manifest_and_terminal_tampering() -> None:
    evidence, properties, gate = _systems()
    required = _requirement(
        EngineeringClaimClass.BUILD_INTEGRITY,
        "build:package-compiles",
    )
    manifest = _manifest(gate, required)
    obligation, _, closure = _closure(
        evidence,
        properties,
        required,
        kind=EngineeringEvidenceKind.COMPILE,
        method=EngineeringProofMethod.COMPILE,
        suffix="snapshot",
    )
    property_gate = gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, closure.receipt_id),),
    )
    base = _BaseClosure(
        receipt_id="eng-closure-snapshot",
        digest="sha256:legacy-snapshot",
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        ready=True,
    )
    gate.bind_terminal_closure(base_closure=base, property_gate_receipt_id=property_gate.receipt_id)

    state = deepcopy(gate.to_state())
    state["manifests"][0]["source_authority_ref"] = "forged:authority"
    with pytest.raises(ValueError, match="manifest|digest"):
        SoftwareEngineeringPropertyGate.from_state(property_evidence=properties, state=state)

    state = deepcopy(gate.to_state())
    state["terminal_closures"][0]["base_closure_digest"] = "sha256:forged"
    with pytest.raises(ValueError, match="terminal|digest|closure"):
        SoftwareEngineeringPropertyGate.from_state(property_evidence=properties, state=state)
