from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.learning_substrate import LearningSubstrate
from nolane.memory.skills import SkillScope


def _verified_personal_skill(runtime: OrganizationRuntime):
    skill = runtime.evolution.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="runtime-governed-learning",
        body="persistent learning must cross the canonical B governance boundary",
    )
    runtime.evolution.verify(
        skill.skill_id,
        EvidenceRecord(
            "runtime-external-verifier",
            "memory.worker",
            True,
            false_accepts=0,
            regressions=0,
        ),
    )
    return skill


def _record_promotion_validation(substrate: LearningSubstrate, skill_id: str) -> None:
    substrate.record_skill_validation(
        skill_id,
        regression_evidence_ids=("runtime-regression-a", "runtime-regression-b"),
        causal_ablation_evidence_ids=("runtime-causal-ablation",),
        regression_evidence_families={
            "runtime-regression-a": "runtime-regression-family-a",
            "runtime-regression-b": "runtime-regression-family-b",
        },
        causal_ablation_evidence_families={
            "runtime-causal-ablation": "runtime-causal-family",
        },
    )


def test_runtime_skill_promotion_crosses_shared_learning_substrate() -> None:
    runtime = OrganizationRuntime.first_generation()
    promoter = runtime.individual_evolution.governed_skill_promoter

    assert isinstance(promoter, LearningSubstrate)
    assert promoter.skills is runtime.evolution
    assert promoter.memory is runtime.memory

    skill = _verified_personal_skill(runtime)
    with pytest.raises(PermissionError, match="executed regression evidence"):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)

    _record_promotion_validation(promoter, skill.skill_id)
    promoted = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL


def test_runtime_restore_preserves_governed_skill_validation_and_shared_authority() -> None:
    runtime = OrganizationRuntime.first_generation()
    promoter = runtime.individual_evolution.governed_skill_promoter
    assert isinstance(promoter, LearningSubstrate)

    skill = _verified_personal_skill(runtime)
    _record_promotion_validation(promoter, skill.skill_id)

    restored = OrganizationRuntime.from_state(runtime.to_state())
    restored_promoter = restored.individual_evolution.governed_skill_promoter

    assert isinstance(restored_promoter, LearningSubstrate)
    assert restored_promoter.skills is restored.evolution
    assert restored_promoter.memory is restored.memory
    assert restored.to_state() == runtime.to_state()

    promoted = restored.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL
