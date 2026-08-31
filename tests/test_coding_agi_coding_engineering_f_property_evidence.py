from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)


PATCH_REF = "patch-property-evidence-0001"
PATCH_DIGEST = "sha256:patch-property-evidence-0001"
SOURCE_REVISION = "git:property-evidence-v1"


def _attest(
    evidence: EngineeringEvidenceLedger,
    *,
    kind: EngineeringEvidenceKind,
    suffix: str,
    source_revision: str = SOURCE_REVISION,
):
    return evidence.record(
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        producer_agent_id="coding.backend.01",
        verifier_agent_id=f"verification.testing.{suffix}",
        verifier_region="verification-testing",
        kind=kind,
        passed=True,
        evidence_refs=(f"run:{suffix}",),
        source_revision=source_revision,
        environment_digest=f"env:{suffix}",
    )


def _ledger() -> tuple[EngineeringEvidenceLedger, EngineeringPropertyEvidenceLedger]:
    evidence = EngineeringEvidenceLedger()
    return evidence, EngineeringPropertyEvidenceLedger(evidence=evidence)


def _obligation(
    ledger: EngineeringPropertyEvidenceLedger,
    claim_class: EngineeringClaimClass,
    property_ref: str,
    *,
    min_independent_sources: int | None = None,
):
    return ledger.register_obligation(
        claim_id=f"claim:{claim_class.value}:{property_ref}",
        claim_class=claim_class,
        property_ref=property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        min_independent_sources=min_independent_sources,
    )


def _witness(
    ledger: EngineeringPropertyEvidenceLedger,
    *,
    obligation,
    attestation,
    method: EngineeringProofMethod,
    role: EngineeringWitnessRole = EngineeringWitnessRole.DIRECT,
    measured_property_ref: str | None = None,
    source_family: str = "independent:test-runner",
    baseline_revision: str | None = None,
    falsifier_ref: str | None = None,
    adversarial: bool = False,
):
    return ledger.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=method,
        role=role,
        measured_property_ref=measured_property_ref or obligation.property_ref,
        oracle_ref=f"oracle:{obligation.property_ref}",
        source_family=source_family,
        baseline_revision=baseline_revision,
        falsifier_ref=falsifier_ref,
        adversarial=adversarial,
    )


def test_functional_behavior_rejects_green_tests_pass_proxy() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:auth-refresh-second-login",
    )
    attestation = _attest(evidence, kind=EngineeringEvidenceKind.TEST, suffix="functional")
    proxy = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.INTEGRATION_TEST,
        measured_property_ref="proxy:tests-pass",
    )

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(proxy.witness_id,))
    assert blocked.ready is False
    assert any(reason.startswith("proxy_measurement:") for reason in blocked.reasons)

    direct = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.INTEGRATION_TEST,
    )
    ready = ledger.assess(obligation.obligation_id, witness_ids=(direct.witness_id,))
    assert ready.ready is True
    assert ready.authority == "candidate_only"


def test_ui_interaction_cannot_be_closed_by_visual_diff_or_screenshot() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.UI_INTERACTION,
        "ui:composer-submit-keyboard-flow",
    )
    visual_attestation = _attest(evidence, kind=EngineeringEvidenceKind.VISUAL, suffix="visual")
    visual = _witness(
        ledger,
        obligation=obligation,
        attestation=visual_attestation,
        method=EngineeringProofMethod.VISUAL_DIFF,
    )

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(visual.witness_id,))
    assert blocked.ready is False
    assert "missing_required_method_group:interaction_e2e" in blocked.reasons

    interaction_attestation = _attest(evidence, kind=EngineeringEvidenceKind.INTERACTION, suffix="interaction")
    interaction = _witness(
        ledger,
        obligation=obligation,
        attestation=interaction_attestation,
        method=EngineeringProofMethod.INTERACTION_E2E,
    )
    ready = ledger.assess(obligation.obligation_id, witness_ids=(interaction.witness_id,))
    assert ready.ready is True


def test_debug_root_cause_requires_reproduction_and_discriminating_falsifier() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.DEBUG_ROOT_CAUSE,
        "root-cause:duplicate-listener-on-second-login",
    )
    reproduction_attestation = _attest(
        evidence,
        kind=EngineeringEvidenceKind.REPRODUCTION,
        suffix="reproduction",
    )
    reproduction = _witness(
        ledger,
        obligation=obligation,
        attestation=reproduction_attestation,
        method=EngineeringProofMethod.REPRODUCTION,
    )

    blocked = ledger.assess(obligation.obligation_id, witness_ids=(reproduction.witness_id,))
    assert blocked.ready is False
    assert "missing_required_method_group:causal_probe|bisect" in blocked.reasons
    assert "missing_falsifier_witness" in blocked.reasons

    causal_attestation = _attest(evidence, kind=EngineeringEvidenceKind.ROOT_CAUSE, suffix="causal")
    causal = _witness(
        ledger,
        obligation=obligation,
        attestation=causal_attestation,
        method=EngineeringProofMethod.CAUSAL_PROBE,
        role=EngineeringWitnessRole.FALSIFIER,
        source_family="independent:causal-replay",
        falsifier_ref="probe:remove-listener-registration-and-replay",
    )
    ready = ledger.assess(
        obligation.obligation_id,
        witness_ids=(reproduction.witness_id, causal.witness_id),
    )
    assert ready.ready is True


def test_regression_preservation_requires_version_bound_baseline() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.REGRESSION_PRESERVATION,
        "regression:existing-auth-contracts",
    )
    regression_attestation = _attest(evidence, kind=EngineeringEvidenceKind.TEST, suffix="regression")
    unbound = _witness(
        ledger,
        obligation=obligation,
        attestation=regression_attestation,
        method=EngineeringProofMethod.REGRESSION_TEST,
        role=EngineeringWitnessRole.REGRESSION,
    )
    blocked = ledger.assess(obligation.obligation_id, witness_ids=(unbound.witness_id,))
    assert blocked.ready is False
    assert "missing_version_bound_baseline" in blocked.reasons

    bound = _witness(
        ledger,
        obligation=obligation,
        attestation=regression_attestation,
        method=EngineeringProofMethod.REGRESSION_TEST,
        role=EngineeringWitnessRole.REGRESSION,
        baseline_revision="git:main-before-patch",
    )
    assert ledger.assess(obligation.obligation_id, witness_ids=(bound.witness_id,)).ready is True


def test_independence_counts_source_families_not_witness_count() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.SECURITY_PROPERTY,
        "security:no-cross-tenant-read",
        min_independent_sources=2,
    )
    a1 = _attest(evidence, kind=EngineeringEvidenceKind.SECURITY, suffix="security-a")
    a2 = _attest(evidence, kind=EngineeringEvidenceKind.SECURITY, suffix="security-b")
    w1 = _witness(
        ledger,
        obligation=obligation,
        attestation=a1,
        method=EngineeringProofMethod.SECURITY_TEST,
        role=EngineeringWitnessRole.ADVERSARIAL,
        source_family="same-upstream:scanner",
        adversarial=True,
    )
    w2 = _witness(
        ledger,
        obligation=obligation,
        attestation=a2,
        method=EngineeringProofMethod.SECURITY_TEST,
        role=EngineeringWitnessRole.ADVERSARIAL,
        source_family="same-upstream:scanner",
        adversarial=True,
    )
    blocked = ledger.assess(obligation.obligation_id, witness_ids=(w1.witness_id, w2.witness_id))
    assert blocked.ready is False
    assert "independent_source_families_below_threshold:1<2" in blocked.reasons

    a3 = _attest(evidence, kind=EngineeringEvidenceKind.SECURITY, suffix="security-c")
    w3 = _witness(
        ledger,
        obligation=obligation,
        attestation=a3,
        method=EngineeringProofMethod.SECURITY_TEST,
        role=EngineeringWitnessRole.ADVERSARIAL,
        source_family="independent:penetration-harness",
        adversarial=True,
    )
    ready = ledger.assess(
        obligation.obligation_id,
        witness_ids=(w1.witness_id, w3.witness_id),
    )
    assert ready.ready is True


def test_revoked_evidence_reopens_property_closure() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.BUILD_INTEGRITY,
        "build:canonical-package-compiles",
    )
    attestation = _attest(evidence, kind=EngineeringEvidenceKind.COMPILE, suffix="compile")
    witness = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.COMPILE,
    )
    assert ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,)).ready is True

    evidence.revoke(attestation.attestation_id, reason="compiler environment later proven invalid")
    reopened = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert reopened.ready is False
    assert f"revoked_or_invalid_attestation:{attestation.attestation_id}" in reopened.reasons


def test_stale_source_revision_cannot_close_current_property() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:current-head-only",
    )
    old_attestation = _attest(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        suffix="stale",
        source_revision="git:old-head",
    )
    witness = _witness(
        ledger,
        obligation=obligation,
        attestation=old_attestation,
        method=EngineeringProofMethod.INTEGRATION_TEST,
    )
    blocked = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert blocked.ready is False
    assert any(reason.startswith("witness_source_revision_mismatch:") for reason in blocked.reasons)


def test_performance_claim_requires_version_bound_benchmark() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.PERFORMANCE_PROPERTY,
        "performance:dispatch-p95-under-budget",
    )
    attestation = _attest(evidence, kind=EngineeringEvidenceKind.PERFORMANCE, suffix="perf")
    witness = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.PERFORMANCE_BENCHMARK,
    )
    blocked = ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,))
    assert "missing_version_bound_baseline" in blocked.reasons

    bound = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.PERFORMANCE_BENCHMARK,
        baseline_revision="git:performance-baseline",
    )
    assert ledger.assess(obligation.obligation_id, witness_ids=(bound.witness_id,)).ready is True


def test_state_restore_rejects_witness_tampering_even_if_shape_is_valid() -> None:
    evidence, ledger = _ledger()
    obligation = _obligation(
        ledger,
        EngineeringClaimClass.UI_VISUAL_FIDELITY,
        "ui:settings-layout-visual-fidelity",
    )
    attestation = _attest(evidence, kind=EngineeringEvidenceKind.VISUAL, suffix="visual-state")
    witness = _witness(
        ledger,
        obligation=obligation,
        attestation=attestation,
        method=EngineeringProofMethod.VISUAL_DIFF,
    )
    assert ledger.assess(obligation.obligation_id, witness_ids=(witness.witness_id,)).ready is True

    state = deepcopy(ledger.to_state())
    state["witnesses"][0]["measured_property_ref"] = "proxy:screenshot-exists"
    with pytest.raises(ValueError, match="digest|witness"):
        EngineeringPropertyEvidenceLedger.from_state(evidence=evidence, state=state)
