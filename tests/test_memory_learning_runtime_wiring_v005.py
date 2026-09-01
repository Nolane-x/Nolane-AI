from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.adaptive_policy import MemoryRetrievalPolicy
from nolane.memory.fabric import MemoryScope
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from nolane.memory.skills import SkillScope


def _verified_personal_skill(runtime: OrganizationRuntime):
    skill = runtime.evolution.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="runtime-governed-learning",
        body="persistent learning must cross the canonical B governance boundary",
    )
    evidence = EvidenceRecord(
        "runtime-external-verifier",
        "memory.worker",
        True,
        false_accepts=0,
        regressions=0,
    )
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(
        skill.skill_id,
        evidence,
        authority_lease_id=lease.lease_id,
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


def test_runtime_b_control_planes_share_single_authority_objects() -> None:
    runtime = OrganizationRuntime.first_generation()

    assert runtime.learning_substrate.memory is runtime.memory
    assert runtime.learning_substrate.skills is runtime.evolution
    assert runtime.learning_substrate.lifecycle is runtime.memory_context.lifecycle
    assert runtime.learning_substrate.relations is runtime.memory_context.relations
    assert runtime.learning_substrate.experiences is runtime.individual_evolution.experiences


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
    assert restored_promoter.lifecycle is restored.memory_context.lifecycle
    assert restored_promoter.relations is restored.memory_context.relations
    assert restored_promoter.experiences is restored.individual_evolution.experiences
    assert restored.to_state() == runtime.to_state()

    promoted = restored.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL


def test_runtime_snapshot_preserves_adaptive_memory_learning_overlay_by_canonical_owner() -> None:
    runtime = OrganizationRuntime.first_generation()
    substrate = runtime.learning_substrate

    anchor = substrate.remember(
        text="runtime verified version anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.PROJECT_STATE,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("runtime-anchor-evidence",),
        source_refs=("runtime-anchor-source",),
        version_scope="runtime-v1",
        salience=0.9,
    )
    health = substrate.record_anchor_health(
        anchor.memory_id,
        actor_agent_id="verification.unit-property.01",
        healthy=True,
        evidence_ref="runtime-anchor-health",
        observed_version_scope="runtime-v1",
        reason="live environment still matches the bound version",
    )
    policy = MemoryRetrievalPolicy(
        information_weight=1.25,
        cost_weight=0.4,
        max_estimated_units=32,
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
        tags=("runtime",),
        policy=policy,
    )

    state = runtime.to_state()
    lifecycle_state = state["memory_learning_lifecycle"]
    retrieval_state = state["memory_learning_retrieval"]
    assert lifecycle_state["metadata"]
    assert lifecycle_state["anchor_health"]
    assert retrieval_state["retrieval_policies"]
    assert retrieval_state["retrieval_receipts"]
    assert retrieval_state["retrieval_snapshots"]

    restored = OrganizationRuntime.from_state(state)
    restored_substrate = restored.learning_substrate

    assert restored_substrate.metadata(anchor.memory_id) == substrate.metadata(anchor.memory_id)
    assert restored_substrate.retrieval_policy(policy.policy_id) == policy
    assert restored_substrate.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt
    assert restored_substrate.anchor_health(anchor.memory_id) == (health,)
    assert restored_substrate.lifecycle is restored.memory_context.lifecycle
    assert restored_substrate.relations is restored.memory_context.relations
    assert restored_substrate.experiences is restored.individual_evolution.experiences
    assert restored.to_state() == state
