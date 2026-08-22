import pytest

from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime


def _subject(runtime: OrganizationRuntime, version: str):
    artifact = runtime.artifacts.put(
        kind='neural-candidate', producer_agent_id='coding.backend.01', content=version,
    )
    return runtime.assurance.register_subject(
        subject_id='SUBJECT-PART12-NEURAL', artifact_id=artifact.artifact_id,
        producer_agent_id='coding.backend.01', subject_version=version,
        policy_class='promotion', evidence_refs=('EV-SUBJECT-P12',),
    )


def _assurance_evidence(runtime, subject, evidence_id, verifier, domain, predecessor):
    return runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id=evidence_id, subject_id=subject.subject_id,
        subject_version=subject.subject_version, verifier_agent_id=verifier,
        domain=domain, passed=True, false_accepts=0, regressions=0,
        sandbox_digest='sandbox-' + evidence_id, heldout_digest='heldout-part12',
        cross_version_refs=(predecessor,), observed_epoch=runtime.assurance.evidence.current_epoch,
        evidence_refs=(evidence_id + '-RAW',),
    ))


def test_neural_challenger_rejects_parameter_ceiling_false_accepts_and_regressions():
    runtime = OrganizationRuntime.first_generation()
    too_large = runtime.individual_evolution.evaluate_neural_challenger(
        agent_id='coding.backend.01', candidate_version='backend-too-large',
        physical_parameters=100_000_000, passed=True, false_accepts=0, regressions=0,
        evidence_ids=('EV-LARGE',),
    )
    assert too_large.accepted is False
    assert too_large.reason == 'parameter_ceiling_exceeded'

    false_accept = runtime.individual_evolution.evaluate_neural_challenger(
        agent_id='coding.backend.01', candidate_version='backend-false-accept',
        physical_parameters=80_000_000, passed=True, false_accepts=1, regressions=0,
        evidence_ids=('EV-FA',),
    )
    assert false_accept.accepted is False
    regression = runtime.individual_evolution.evaluate_neural_challenger(
        agent_id='coding.backend.01', candidate_version='backend-regression',
        physical_parameters=80_000_000, passed=True, false_accepts=0, regressions=1,
        evidence_ids=('EV-REG',),
    )
    assert regression.accepted is False


def test_production_neural_promotion_requires_part8_assurance_and_rolls_back_exact_predecessor():
    runtime = OrganizationRuntime.first_generation()
    agent_id = 'coding.backend.01'
    predecessor = runtime.registry.get(agent_id).neural_version
    candidate = 'NUC-0.1+coding.backend.01-delta-0.2'
    subject = _subject(runtime, candidate)
    low = runtime.individual_evolution.evaluate_neural_challenger(
        agent_id=agent_id, candidate_version=candidate, physical_parameters=80_000_000,
        passed=True, false_accepts=0, regressions=0, evidence_ids=('EV-LOW-P12',),
    )
    assert low.accepted is True

    with pytest.raises(PermissionError):
        runtime.individual_evolution.promote_neural_challenger(
            agent_id=agent_id, subject_id=subject.subject_id,
            assurance_evidence_ids=(), candidate_receipt_id=low.receipt_id,
        )

    unit = _assurance_evidence(
        runtime, subject, 'EV-P12-UNIT', 'verification.unit-property.01',
        AssuranceDomain.UNIT_PROPERTY, predecessor,
    )
    fuzz = _assurance_evidence(
        runtime, subject, 'EV-P12-FUZZ', 'verification.fuzz-regression.01',
        AssuranceDomain.FUZZ_REGRESSION, predecessor,
    )
    promoted = runtime.individual_evolution.promote_neural_challenger(
        agent_id=agent_id, subject_id=subject.subject_id,
        assurance_evidence_ids=(unit.evidence_id, fuzz.evidence_id),
        candidate_receipt_id=low.receipt_id,
    )
    assert promoted.promoted is True
    assert runtime.registry.get(agent_id).neural_version == candidate
    assert runtime.individual_evolution.lineage_for(agent_id)[-1].transition == 'neural_promoted'

    rollback = runtime.individual_evolution.rollback_neural(
        agent_id=agent_id, reason='post-promotion hidden regression',
    )
    assert rollback.restored_version == predecessor
    assert runtime.registry.get(agent_id).neural_version == predecessor
    assert runtime.individual_evolution.lineage_for(agent_id)[-1].transition == 'neural_rolled_back'
