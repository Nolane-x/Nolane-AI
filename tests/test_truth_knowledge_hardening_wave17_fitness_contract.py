from __future__ import annotations

import importlib

import pytest

from nolane.external_core.evidence_observation_fitness_truth import (
    FitnessCheckAssessment,
    FitnessCheckStatus,
)
from nolane.external_core.knowledge_observation_fitness_truth import (
    FitnessCheck,
    ObservationFitnessRequirementRevision,
)


_A17_SIDECARS = (
    ("nolane.external_core.evidence_observation_fitness_truth", "external.evidence"),
    ("nolane.external_core.knowledge_observation_fitness_truth", "external.knowledge"),
    ("nolane.external_core.epistemic_observation_fitness_truth", "external.epistemic"),
    ("nolane.external_core.verification_observation_fitness_truth", "external.verification"),
    ("nolane.external_core.assurance_observation_fitness_truth", "external.assurance"),
)


@pytest.mark.parametrize(("module_name", "parent_id"), _A17_SIDECARS)
def test_a17_fitness_sidecars_bind_existing_parent_without_new_authority(
    module_name: str,
    parent_id: str,
):
    module = importlib.import_module(module_name)
    assert module.PARENT_COMPONENT_ID == parent_id
    assert not hasattr(module, "COMPONENT_ID")


def test_a17_fitness_sidecars_cover_exactly_five_family_a_parents():
    parents = {
        importlib.import_module(module_name).PARENT_COMPONENT_ID
        for module_name, _ in _A17_SIDECARS
    }
    assert parents == {
        "external.evidence",
        "external.knowledge",
        "external.epistemic",
        "external.verification",
        "external.assurance",
    }


def test_a17_fitness_is_categorical_not_scalar_confidence():
    assert {value.value for value in FitnessCheck} == {
        "calibration",
        "integrity",
        "resolution",
        "synchronization",
        "interference",
    }
    assert {value.value for value in FitnessCheckStatus} == {
        "pass",
        "fail",
        "unknown",
    }
    row = FitnessCheckAssessment.create(
        check=FitnessCheck.CALIBRATION,
        status=FitnessCheckStatus.PASS,
    )
    assert row.status is FitnessCheckStatus.PASS
    assert not hasattr(row, "confidence")


def test_a17_requirement_requires_explicit_nonempty_check_set():
    from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
    from nolane.external_core.knowledge_observation_truth import ObservationRequirement
    from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger

    evidence = EvidenceLedger()
    support = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence:a17-red",
            subject_id="claim:a17-red",
            source_id="source:a17-red",
            source_family="family:a17-red",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:a17-red",
        )
    )
    knowledge = KnowledgeLedger()
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim:a17-red",
            subject="sensor",
            relation="healthy",
            object="yes",
            evidence_ids=(support.evidence_id,),
        )
    )
    observation = ObservationRequirement.create(
        claim=claim,
        observation_id="observation:a17-red",
        channel=EvidenceChannel.OBSERVATION,
    )
    with pytest.raises(ValueError, match="fitness checks"):
        ObservationFitnessRequirementRevision.create(
            observation_requirement=observation,
            checks=(),
        )
