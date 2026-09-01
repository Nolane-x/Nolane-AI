from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.skills import SkillEvolutionEngine, SkillScope


def _clean_evidence(evidence_id: str, verifier_agent_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id,
        verifier_agent_id,
        True,
        false_accepts=0,
        regressions=0,
    )


def _verify_runtime_skill(runtime: OrganizationRuntime):
    skill = runtime.evolution.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="governed-promotion-v013",
        body="promotion authority must remain runtime governed",
    )
    evidence = _clean_evidence("v013-external-verification", "memory.worker")
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(skill.skill_id, evidence, authority_lease_id=lease.lease_id)
    return skill


def _record_governed_validation(runtime: OrganizationRuntime, skill_id: str) -> None:
    runtime.learning_substrate.record_skill_validation(
        skill_id,
        regression_evidence_ids=("v013-regression-a", "v013-regression-b"),
        causal_ablation_evidence_ids=("v013-causal-ablation",),
        regression_evidence_families={
            "v013-regression-a": "v013-regression-family-a",
            "v013-regression-b": "v013-regression-family-b",
        },
        causal_ablation_evidence_families={
            "v013-causal-ablation": "v013-causal-family",
        },
    )


def test_canonical_runtime_blocks_direct_skill_promotion_bypass() -> None:
    runtime = OrganizationRuntime.first_generation()
    skill = _verify_runtime_skill(runtime)

    with pytest.raises(PermissionError, match="governed skill promotion"):
        runtime.evolution.promote(skill.skill_id, SkillScope.PERSONAL)

    with pytest.raises(PermissionError, match="executed regression evidence"):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)

    _record_governed_validation(runtime, skill.skill_id)
    promoted = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL


def test_skill_owner_cannot_supply_its_own_independent_verification() -> None:
    engine = SkillEvolutionEngine()
    skill = engine.propose(
        owner_agent_id="agent-a",
        region="coding",
        name="self-verified-skill",
        body="self evidence must not count as independent verification",
    )
    self_evidence = _clean_evidence("v013-self-evidence", skill.owner_agent_id)

    with pytest.raises(PermissionError, match="owner.*independent verifier"):
        engine.verify(skill.skill_id, self_evidence)


def test_restore_rejects_promoted_skill_laundered_through_owner_self_evidence() -> None:
    engine = SkillEvolutionEngine()
    skill = engine.propose(
        owner_agent_id="agent-a",
        region="coding",
        name="restore-self-verification",
        body="serialized promotion must preserve independent verification",
    )
    self_evidence = _clean_evidence("v013-restore-self-evidence", skill.owner_agent_id)

    forged_row = skill.to_state()
    forged_row["scope"] = SkillScope.PERSONAL.value
    forged_row["evidence"] = [self_evidence.to_state()]

    with pytest.raises((PermissionError, ValueError), match="owner.*independent verifier"):
        SkillEvolutionEngine.from_state({"skills": [forged_row]})
