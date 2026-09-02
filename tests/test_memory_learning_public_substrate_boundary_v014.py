from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory import LearningSubstrate
from nolane.memory.skills import SkillScope


def _public_substrate() -> LearningSubstrate:
    runtime = OrganizationRuntime.first_generation()
    return LearningSubstrate(registry=runtime.registry, events=runtime.ledger)


def _verified_candidate(substrate: LearningSubstrate):
    skill = substrate.skills.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="public-substrate-governed-promotion-v014",
        body="public LearningSubstrate must own its skill promotion policy boundary",
    )
    evidence = EvidenceRecord(
        "v014-independent-verification",
        "memory.worker",
        True,
        false_accepts=0,
        regressions=0,
    )
    lease = substrate.learning_authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=substrate.skills.verification_subject_digest(skill.skill_id),
    )
    substrate.skills.verify(skill.skill_id, evidence, authority_lease_id=lease.lease_id)
    return skill


def test_public_learning_substrate_blocks_direct_skill_engine_promotion_bypass() -> None:
    substrate = _public_substrate()
    skill = _verified_candidate(substrate)

    with pytest.raises(PermissionError, match="governed skill promotion.*executed regression evidence"):
        substrate.skills.promote(skill.skill_id, SkillScope.PERSONAL)

    assert substrate.skills.get(skill.skill_id).scope is SkillScope.CANDIDATE
