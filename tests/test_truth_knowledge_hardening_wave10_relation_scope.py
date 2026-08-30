from __future__ import annotations

from copy import deepcopy

from nolane.external_core.epistemic_truth import EpistemicDisposition, EpistemicJudge, TruthRelationAwareScope
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry, RelationSemanticsRevision


def evidence(evidence_id: str, claim_id: str, *, source: str, family: str, channel: EvidenceChannel) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=claim_id,
        source_id=source,
        source_family=family,
        channel=channel,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
    )


def registry_with(relation: str, cardinality: RelationCardinality) -> RelationSemanticsRegistry:
    registry = RelationSemanticsRegistry()
    registry.record(RelationSemanticsRevision.create(
        relation=relation,
        revision=1,
        cardinality=cardinality,
    ))
    return registry


def two_value_system(*, relation: str, object_a: str, object_b: str):
    ev = EvidenceLedger()
    ev.record(evidence("e-a", "claim.a", source="source-a", family="family-a", channel=EvidenceChannel.TEST))
    ev.record(evidence("e-b", "claim.b", source="source-b", family="family-b", channel=EvidenceChannel.REPRODUCTION))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.a", subject="subject", relation=relation, object=object_a,
        risk=KnowledgeRisk.STANDARD, evidence_ids=("e-a",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.b", subject="subject", relation=relation, object=object_b,
        risk=KnowledgeRisk.STANDARD, evidence_ids=("e-b",),
    ))
    return knowledge, ev


def test_a10_multi_valued_relation_does_not_create_false_competitor_or_contradiction():
    knowledge, ev = two_value_system(relation="speaks", object_a="English", object_b="French")
    relations = registry_with("speaks", RelationCardinality.MULTI_VALUED)

    assert knowledge.truth_scope_claim_ids_v3("claim.a", relations) == ("claim.a",)
    scope = EpistemicJudge().relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )

    assert isinstance(scope, TruthRelationAwareScope)
    assert scope.assessment("claim.a").disposition is EpistemicDisposition.SUPPORTED
    assert scope.scope_claim_ids == ("claim.a",)
    assert scope.relation_ids == ("speaks",)
    assert not scope.contradictions
    assert not any(row.reason == "relation_semantics_unspecified_for_multiple_values" for row in scope.debts)


def test_a10_exclusive_relation_keeps_distinct_supported_objects_as_competitors():
    knowledge, ev = two_value_system(relation="status", object_a="online", object_b="offline")
    relations = registry_with("status", RelationCardinality.EXCLUSIVE)

    assert set(knowledge.truth_scope_claim_ids_v3("claim.a", relations)) == {"claim.a", "claim.b"}
    scope = EpistemicJudge().relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )

    assert len(scope.contradictions) == 1
    assert set(scope.contradictions[0].claim_ids) == {"claim.a", "claim.b"}
    assert any(row.reason == "competing_supported_propositions" for row in scope.debts)


def test_a10_unspecified_relation_preserves_neighborhood_as_explicit_ambiguity_not_fake_conflict():
    knowledge, ev = two_value_system(relation="speaks", object_a="English", object_b="French")
    relations = RelationSemanticsRegistry()

    scope = EpistemicJudge().relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )

    assert set(scope.scope_claim_ids) == {"claim.a", "claim.b"}
    assert not scope.contradictions
    ambiguous = tuple(row for row in scope.debts if row.reason == "relation_semantics_unspecified_for_multiple_values")
    assert {row.claim_id for row in ambiguous} == {"claim.a", "claim.b"}


def test_a10_exclusive_competitor_for_ancestor_is_in_descendant_fixed_point_scope():
    ev = EvidenceLedger()
    ev.record(evidence("parent-e", "claim.parent", source="parent", family="parent-family", channel=EvidenceChannel.TEST))
    ev.record(evidence("parent-alt-e", "claim.parent.alt", source="parent-alt", family="parent-alt-family", channel=EvidenceChannel.ADVERSARIAL))
    ev.record(evidence("child-e", "claim.child", source="child", family="child-family", channel=EvidenceChannel.REPRODUCTION))

    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent", subject="server", relation="status", object="online",
        evidence_ids=("parent-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent.alt", subject="server", relation="status", object="offline",
        evidence_ids=("parent-alt-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.child", subject="deployment", relation="depends", object="server",
        evidence_ids=("child-e",), parent_claim_ids=("claim.parent",),
    ))

    relations = RelationSemanticsRegistry()
    relations.record(RelationSemanticsRevision.create(
        relation="status", revision=1, cardinality=RelationCardinality.EXCLUSIVE,
    ))
    relations.record(RelationSemanticsRevision.create(
        relation="depends", revision=1, cardinality=RelationCardinality.EXCLUSIVE,
    ))

    scope = EpistemicJudge().relation_aware_dependency_scope(
        "claim.child", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
    assert scope.lineage_claim_ids == ("claim.child", "claim.parent")
    assert set(scope.scope_claim_ids) == {"claim.child", "claim.parent", "claim.parent.alt"}
    assert any("claim.parent" in row.claim_ids for row in scope.contradictions)


def test_a10_relation_policy_digest_is_scoped_and_live_revalidated():
    knowledge, ev = two_value_system(relation="speaks", object_a="English", object_b="French")
    relations = registry_with("speaks", RelationCardinality.MULTI_VALUED)
    judge = EpistemicJudge()
    original = judge.relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )

    relations.record(RelationSemanticsRevision.create(
        relation="status", revision=1, cardinality=RelationCardinality.EXCLUSIVE,
    ))
    unrelated = judge.relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
    assert unrelated.digest == original.digest
    assert judge.validate_relation_aware_scope(
        original, knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )

    current = relations.current("speaks")
    assert current is not None
    relations.record(RelationSemanticsRevision.create(
        relation="speaks",
        revision=2,
        cardinality=RelationCardinality.EXCLUSIVE,
        previous_digest=current.digest,
    ))
    changed = judge.relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
    assert changed.digest != original.digest
    assert not judge.validate_relation_aware_scope(
        original, knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )


def test_a10_relation_aware_scope_roundtrip_is_tamper_evident_but_not_self_authenticating():
    knowledge, ev = two_value_system(relation="status", object_a="online", object_b="offline")
    relations = registry_with("status", RelationCardinality.EXCLUSIVE)
    judge = EpistemicJudge()
    scope = judge.relation_aware_dependency_scope(
        "claim.a", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
    assert TruthRelationAwareScope.from_state(deepcopy(scope.to_state())) == scope

    forged_state = deepcopy(scope.to_state())
    forged_state["relation_ids"] = []
    forged_state["digest"] = TruthRelationAwareScope.create_from_state_payload(forged_state).digest
    forged = TruthRelationAwareScope.from_state(forged_state)
    assert not judge.validate_relation_aware_scope(
        forged, knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
