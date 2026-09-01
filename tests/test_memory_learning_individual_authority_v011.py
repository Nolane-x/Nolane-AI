from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord


def _memory_evidence(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        "verification.unit-property.01",
        True,
        false_accepts=0,
        regressions=0,
        notes="independent Memory/Learning verification",
    )


def test_individual_evolution_skill_verification_forwards_exact_authority_lease() -> None:
    runtime = OrganizationRuntime.first_generation()
    authority = runtime.learning_substrate.learning_authority
    skill = runtime.evolution.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="authority-forwarded-skill",
        body="positive skill evidence must cross the shared B authority",
    )
    evidence = _memory_evidence("individual-skill-proof")
    lease = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )

    with pytest.raises(PermissionError, match="preissued learning evidence lease"):
        runtime.individual_evolution.verify_skill(skill.skill_id, evidence)

    verified = runtime.individual_evolution.verify_skill(
        skill.skill_id,
        evidence,
        authority_lease_id=lease.lease_id,
    )
    assert verified.evidence == (evidence,)
    assert len(authority.uses_for(lease.lease_id)) == 1


def test_individual_evolution_self_model_update_forwards_exact_authority_lease() -> None:
    runtime = OrganizationRuntime.first_generation()
    authority = runtime.learning_substrate.learning_authority
    evidence = _memory_evidence("individual-self-model-proof")
    digest = runtime.individual_evolution.self_models.competence_subject_digest(
        "memory.chief",
        domain="memory-governance",
        score=0.82,
    )
    lease = authority.issue(
        subject_kind="self_model",
        subject_id="memory.chief",
        operation_class="self_model.update_competence",
        producer_agent_id="memory.chief",
        evidence=evidence,
        subject_digest=digest,
    )

    updated = runtime.individual_evolution.update_self_model(
        agent_id="memory.chief",
        domain="memory-governance",
        score=0.82,
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    assert dict(updated.domain_competence)["memory-governance"] == 0.82
    assert len(authority.uses_for(lease.lease_id)) == 1
    assert runtime.individual_evolution.lineage_for("memory.chief")[-1].transition == "self_model_updated"


def test_longitudinal_benchmark_observation_requires_exact_subject_bound_lease() -> None:
    runtime = OrganizationRuntime.first_generation()
    individual = runtime.individual_evolution
    authority = runtime.learning_substrate.learning_authority
    evidence = _memory_evidence("individual-benchmark-proof")
    digest = individual.benchmark_subject_digest(
        agent_id="memory.chief",
        observation_id="memory-benchmark-observation-1",
        benchmark_id="memory-governance-benchmark",
        regime_digest="regime-v1-digest",
        score=0.91,
        regressions=0,
    )
    lease = authority.issue(
        subject_kind="individual_evolution",
        subject_id="memory.chief",
        operation_class="individual_evolution.record_benchmark_observation",
        producer_agent_id="memory.chief",
        evidence=evidence,
        subject_digest=digest,
    )

    with pytest.raises(PermissionError, match="preissued learning evidence lease"):
        individual.record_benchmark_observation(
            observation_id="memory-benchmark-observation-1",
            agent_id="memory.chief",
            benchmark_id="memory-governance-benchmark",
            regime_digest="regime-v1-digest",
            score=0.91,
            regressions=0,
            evidence=evidence,
        )

    observation = individual.record_benchmark_observation(
        observation_id="memory-benchmark-observation-1",
        agent_id="memory.chief",
        benchmark_id="memory-governance-benchmark",
        regime_digest="regime-v1-digest",
        score=0.91,
        regressions=0,
        evidence=evidence,
        authority_lease_id=lease.lease_id,
    )
    assert observation.observation_id == "memory-benchmark-observation-1"
    assert authority.uses_for(lease.lease_id)[0].use_ref.endswith(
        "memory-benchmark-observation-1"
    )
