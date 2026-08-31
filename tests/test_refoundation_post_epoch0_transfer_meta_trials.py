from __future__ import annotations

import inspect

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.reasoning_invention import TransferIntent
from nolane.memory.experience import (
    AttributionRecord,
    ExperienceLedger,
    ExperienceOutcome,
    ExperienceRecord,
    LearningLayer,
)
from nolane.metadata.component_versions import component_version


def _experience_ledger():
    evidence = EvidenceRecord("evidence:c6:source", "verification.c6.source", True)
    source = ExperienceRecord(
        experience_id="experience:c6:source",
        agent_id="source.c6.agent",
        region="source-region",
        domain="repository-repair",
        outcome=ExperienceOutcome.SUCCESS,
        summary="C6 source experience",
        task_id="task:c6:source",
        object_refs=("object:c6:source",),
        evidence_refs=(evidence.evidence_id,),
    )
    attribution = AttributionRecord(
        attribution_id="attribution:c6:source",
        experience_id=source.experience_id,
        agent_id=source.agent_id,
        learning_layer=LearningLayer.STRATEGY,
        lesson="Preserve bounded causal structure while adapting surface policy.",
        positive=True,
        verifier_agent_id=evidence.verifier_agent_id,
        evidence=evidence,
    )
    ledger = object.__new__(ExperienceLedger)
    ledger._experiences = {source.experience_id: source}
    ledger._attributions = {attribution.attribution_id: attribution}
    return ledger, source, attribution


def _intent(source_receipt_id: str) -> TransferIntent:
    return TransferIntent(
        source_domain="repository-repair",
        target_domain="incident-response",
        source_receipt_ids=(source_receipt_id,),
        verified_challenge_ids=("challenge:c6:verified",),
        generalized_variables=("dependency-order", "failure-surface"),
        invariants=("bounded-side-effects", "causal-precedence"),
        target_assumptions=("finite-action-space",),
        transfer_trial_ids=("trial:c6:holdout", "trial:c6:perturbation"),
    )


def _promotion_receipt(
    *,
    transfer_id: str,
    predecessor_version: str,
    evidence_ids: tuple[str, ...],
) -> PromotionAssuranceReceipt:
    payload = {
        "receipt_id": "assurance-promotion-c6",
        "subject_id": transfer_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": predecessor_version,
        "verifier_ids": ["verification.c6.alpha", "verification.c6.beta"],
        "authorized": True,
        "reasons": [],
    }
    return PromotionAssuranceReceipt(
        receipt_id=payload["receipt_id"],
        subject_id=transfer_id,
        evidence_ids=evidence_ids,
        predecessor_version=predecessor_version,
        verifier_ids=("verification.c6.alpha", "verification.c6.beta"),
        authorized=True,
        reasons=(),
        digest=canonical_digest(payload),
    )


def _assurance_plane(receipt: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {receipt.receipt_id: receipt}
    return plane


def test_c6_revision_declares_destination_trial_governance() -> None:
    import nolane.external_core.transfer_meta as native
    import nolane.external_core.transfer_trials as trials

    assert str(component_version("external.transfer_meta")) == "0.0.2"
    assert native.COMPONENT_VERSION == trials.COMPONENT_VERSION == "0.0.2"
    assert native.COMPONENT_ID == trials.COMPONENT_ID == "external.transfer_meta"
    for name in (
        "TransferTrialEnvelope",
        "DestinationTrialResult",
        "DestinationTrialMatrix",
        "NegativeTransferRegimeRecord",
    ):
        assert hasattr(trials, name), name


def test_c6_trial_envelope_binds_exact_transfer_intent_and_adaptation() -> None:
    from nolane.external_core.transfer_meta import PortableExperience, TransferAdaptation
    from nolane.external_core.transfer_trials import TransferTrialEnvelope

    portable = PortableExperience.create(
        source_domain="repository-repair",
        learning_layer="strategy",
        lesson="Preserve causal precedence.",
    )
    intent = _intent("transfer-source-receipt:c6")
    adaptation = TransferAdaptation.create(
        portable,
        target_domain="incident-response",
        metadata={"budget": 4},
    )
    first = TransferTrialEnvelope.create(intent, adaptation)
    second = TransferTrialEnvelope.create(intent, adaptation)

    assert first == second
    assert first.transfer_intent_id == intent.transfer_intent_id
    assert first.transfer_id == adaptation.transfer_id
    assert first.generalized_variables == intent.generalized_variables
    assert first.invariants == intent.invariants
    assert first.required_trial_ids == intent.transfer_trial_ids
    assert TransferTrialEnvelope.from_state(first.to_state()) == first

    wrong_target = TransferIntent(
        source_domain=intent.source_domain,
        target_domain="security-review",
        source_receipt_ids=intent.source_receipt_ids,
        verified_challenge_ids=intent.verified_challenge_ids,
        generalized_variables=intent.generalized_variables,
        invariants=intent.invariants,
        target_assumptions=intent.target_assumptions,
        transfer_trial_ids=intent.transfer_trial_ids,
    )
    with pytest.raises(ValueError, match="target|domain"):
        TransferTrialEnvelope.create(wrong_target, adaptation)


def test_c6_destination_matrix_requires_exact_trial_coverage_invariants_and_independent_verifiers() -> None:
    from nolane.external_core.transfer_meta import PortableExperience, TransferAdaptation
    from nolane.external_core.transfer_trials import (
        DestinationTrialMatrix,
        DestinationTrialResult,
        TransferTrialEnvelope,
    )

    portable = PortableExperience.create(
        source_domain="repository-repair",
        learning_layer="strategy",
        lesson="Preserve causal precedence.",
    )
    intent = _intent("transfer-source-receipt:c6")
    adaptation = TransferAdaptation.create(portable, target_domain=intent.target_domain, metadata={})
    envelope = TransferTrialEnvelope.create(intent, adaptation)
    holdout = DestinationTrialResult(
        trial_id="trial:c6:holdout",
        target_regime_id="regime:c6:linux",
        verifier_id="verification.c6.alpha",
        evidence_id="evidence:c6:holdout",
        passed=True,
        violated_invariant_ids=(),
    )
    perturbation = DestinationTrialResult(
        trial_id="trial:c6:perturbation",
        target_regime_id="regime:c6:windows",
        verifier_id="verification.c6.beta",
        evidence_id="evidence:c6:perturbation",
        passed=True,
        violated_invariant_ids=(),
    )
    matrix = DestinationTrialMatrix.create(envelope, (perturbation, holdout))

    assert matrix.passed is True
    assert matrix.evidence_ids == ("evidence:c6:holdout", "evidence:c6:perturbation")
    assert matrix.target_regime_ids == ("regime:c6:linux", "regime:c6:windows")
    assert DestinationTrialMatrix.from_state(matrix.to_state()) == matrix

    with pytest.raises(ValueError, match="coverage|trial"):
        DestinationTrialMatrix.create(envelope, (holdout,))
    with pytest.raises(ValueError, match="independent|verifier"):
        DestinationTrialMatrix.create(
            envelope,
            (
                holdout,
                DestinationTrialResult(
                    trial_id="trial:c6:perturbation",
                    target_regime_id="regime:c6:windows",
                    verifier_id=holdout.verifier_id,
                    evidence_id="evidence:c6:perturbation",
                    passed=True,
                    violated_invariant_ids=(),
                ),
            ),
        )

    violated = DestinationTrialResult(
        trial_id="trial:c6:perturbation",
        target_regime_id="regime:c6:windows",
        verifier_id="verification.c6.beta",
        evidence_id="evidence:c6:violated",
        passed=False,
        violated_invariant_ids=("causal-precedence",),
    )
    failed = DestinationTrialMatrix.create(envelope, (holdout, violated))
    assert failed.passed is False
    assert failed.violated_invariant_ids == ("causal-precedence",)


def test_c6_governor_requires_intent_matrix_and_assurance_binding_before_acceptance() -> None:
    import nolane.external_core.transfer_meta as native
    from nolane.external_core.transfer_trials import DestinationTrialResult

    ledger, source, attribution = _experience_ledger()
    governor = native.TransferMetaGovernor(experience=ledger)
    portable, source_receipt = governor.compile_portable(source.experience_id, attribution.attribution_id)
    intent = _intent(source_receipt.receipt_id)

    assert "intent" in inspect.signature(governor.propose).parameters
    assert "trial_matrix_id" in inspect.signature(governor.accept).parameters
    record = governor.propose(
        portable.portable_id,
        intent=intent,
        metadata={"budget": 4},
    )
    assert record.transfer_intent_id == intent.transfer_intent_id
    assert record.trial_matrix_id is None

    with pytest.raises(ValueError, match="trial|matrix"):
        governor.accept(
            record.adaptation.transfer_id,
            assurance=object(),
            receipt=object(),
            evidence_ids=("evidence:any",),
            trial_matrix_id="matrix:missing",
        )

    matrix = governor.record_destination_trials(
        record.adaptation.transfer_id,
        results=(
            DestinationTrialResult(
                trial_id="trial:c6:holdout",
                target_regime_id="regime:c6:linux",
                verifier_id="verification.c6.alpha",
                evidence_id="evidence:c6:holdout",
                passed=True,
                violated_invariant_ids=(),
            ),
            DestinationTrialResult(
                trial_id="trial:c6:perturbation",
                target_regime_id="regime:c6:windows",
                verifier_id="verification.c6.beta",
                evidence_id="evidence:c6:perturbation",
                passed=True,
                violated_invariant_ids=(),
            ),
        ),
    )
    evidence_ids = (matrix.matrix_id, *matrix.evidence_ids)
    receipt = _promotion_receipt(
        transfer_id=record.adaptation.transfer_id,
        predecessor_version=source_receipt.source_authority_digest,
        evidence_ids=evidence_ids,
    )
    accepted = governor.accept(
        record.adaptation.transfer_id,
        assurance=_assurance_plane(receipt),
        receipt=receipt,
        evidence_ids=evidence_ids,
        trial_matrix_id=matrix.matrix_id,
    )
    assert accepted.state is native.TransferState.ACCEPTED
    assert accepted.trial_matrix_id == matrix.matrix_id


def test_c6_negative_transfer_records_target_regime_and_blocks_reuse() -> None:
    import nolane.external_core.transfer_meta as native
    from nolane.external_core.transfer_trials import DestinationTrialResult

    ledger, source, attribution = _experience_ledger()
    governor = native.TransferMetaGovernor(experience=ledger)
    portable, source_receipt = governor.compile_portable(source.experience_id, attribution.attribution_id)
    intent = _intent(source_receipt.receipt_id)
    record = governor.propose(portable.portable_id, intent=intent, metadata={})
    matrix = governor.record_destination_trials(
        record.adaptation.transfer_id,
        results=(
            DestinationTrialResult(
                trial_id="trial:c6:holdout",
                target_regime_id="regime:c6:linux",
                verifier_id="verification.c6.alpha",
                evidence_id="evidence:c6:holdout",
                passed=True,
                violated_invariant_ids=(),
            ),
            DestinationTrialResult(
                trial_id="trial:c6:perturbation",
                target_regime_id="regime:c6:windows",
                verifier_id="verification.c6.beta",
                evidence_id="evidence:c6:perturbation",
                passed=True,
                violated_invariant_ids=(),
            ),
        ),
    )
    evidence_ids = (matrix.matrix_id, *matrix.evidence_ids)
    receipt = _promotion_receipt(
        transfer_id=record.adaptation.transfer_id,
        predecessor_version=source_receipt.source_authority_digest,
        evidence_ids=evidence_ids,
    )
    governor.accept(
        record.adaptation.transfer_id,
        assurance=_assurance_plane(receipt),
        receipt=receipt,
        evidence_ids=evidence_ids,
        trial_matrix_id=matrix.matrix_id,
    )

    negative = governor.report_negative_transfer(
        record.adaptation.transfer_id,
        target_regime_id="regime:c6:windows",
        evidence_ids=("evidence:c6:negative",),
        reason="target-regime regression",
    )
    assert negative.target_regime_id == "regime:c6:windows"
    assert negative.transfer_id == record.adaptation.transfer_id
    assert governor.negative_transfer_records(
        target_domain="incident-response",
        target_regime_id="regime:c6:windows",
    ) == (negative,)
    assert governor.record(record.adaptation.transfer_id).state is native.TransferState.QUARANTINED
    assert governor.reusable_ids() == ()
